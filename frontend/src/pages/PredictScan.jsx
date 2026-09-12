import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPatient } from '../api/patients';
import { predictScan } from '../api/predict';

const DISEASE_OPTIONS = [
  {
    value: 'brain_tumor',
    label: 'Brain Tumor Classifier',
    description: 'Glioma, Meningioma, Pituitary, or No Tumor (BRISC 2025)',
  },
  {
    value: 'alzheimers',
    label: "Alzheimer's Disease Classifier",
    description: 'Dementia Staging (Non, Very Mild, Mild, Moderate)',
  },
];

export default function PredictScan() {
  const { id } = useParams();
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  // 1. Patient state
  const [patient, setPatient] = useState(null);
  const [patientLoading, setPatientLoading] = useState(true);
  const [patientError, setPatientError] = useState(null);
  const [isNotFound, setIsNotFound] = useState(false);

  // 2. Form state
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [diseaseType, setDiseaseType] = useState('brain_tumor');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [sliceIndex, setSliceIndex] = useState('');
  const [brightnessThreshold, setBrightnessThreshold] = useState('0.15');
  const [erosionPixels, setErosionPixels] = useState('12');

  // 3. Inference & Results state
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [predictionResult, setPredictionResult] = useState(null);

  // Fetch Patient info
  const fetchPatientData = useCallback(async () => {
    try {
      setPatientLoading(true);
      setPatientError(null);
      setIsNotFound(false);
      const data = await getPatient(id);
      setPatient(data);
    } catch (err) {
      if (err.response?.status === 404) {
        setIsNotFound(true);
      } else {
        const msg =
          err.response?.data?.detail ||
          err.message ||
          'Failed to load patient record.';
        setPatientError(msg);
      }
    } finally {
      setPatientLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchPatientData();
  }, [fetchPatientData]);

  // Handle file selection & preview generation
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Revoke previous object URL if any
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }

    setSelectedFile(file);
    setSubmitError(null);

    const isImage =
      file.type.startsWith('image/') ||
      file.name.toLowerCase().endsWith('.jpg') ||
      file.name.toLowerCase().endsWith('.jpeg') ||
      file.name.toLowerCase().endsWith('.png');

    if (isImage) {
      const objUrl = URL.createObjectURL(file);
      setPreviewUrl(objUrl);
    } else {
      setPreviewUrl(null);
    }
  };

  const clearSelectedFile = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(null);
    setPreviewUrl(null);
  };

  // Cleanup object URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  // Handle Form Submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile || !diseaseType || submitting || !patient) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      // Backend POST /predict expects patient_id to be the patient's string MRN
      formData.append('patient_id', patient.mrn);
      formData.append('disease_type', diseaseType);

      if (sliceIndex !== '' && !isNaN(parseInt(sliceIndex, 10))) {
        formData.append('slice_index', parseInt(sliceIndex, 10));
      }
      if (brightnessThreshold !== '' && !isNaN(parseFloat(brightnessThreshold))) {
        formData.append('gradcam_brightness_threshold', parseFloat(brightnessThreshold));
      }
      if (erosionPixels !== '' && !isNaN(parseInt(erosionPixels, 10))) {
        formData.append('gradcam_erosion_pixels', parseInt(erosionPixels, 10));
      }

      const result = await predictScan(formData);
      setPredictionResult(result);
    } catch (err) {
      const serverDetail = err.response?.data?.detail;
      let readableError;
      if (typeof serverDetail === 'string') {
        readableError = serverDetail;
      } else if (Array.isArray(serverDetail) && serverDetail.length > 0) {
        readableError = serverDetail.map((d) => d.msg || JSON.stringify(d)).join(', ');
      } else {
        readableError = err.message || 'Inference analysis failed. Please check the scan format.';
      }
      setSubmitError(readableError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setPredictionResult(null);
    setSubmitError(null);
    clearSelectedFile();
    setSliceIndex('');
  };

  // Helper to format class probabilities list sorted descending
  const sortedProbabilities = useMemo(() => {
    if (!predictionResult?.all_class_probabilities) return [];
    return Object.entries(predictionResult.all_class_probabilities)
      .map(([className, prob]) => ({
        className,
        probability: Number(prob),
        percentage: (Number(prob) * 100).toFixed(1),
      }))
      .sort((a, b) => b.probability - a.probability);
  }, [predictionResult]);

  // Helper to label classes cleanly
  const formatClassLabel = (label) => {
    if (!label) return '—';
    return label
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const isNegativeClass = (className) => {
    const lower = (className || '').toLowerCase();
    return lower === 'no_tumor' || lower === 'non_demented';
  };

  // 1. Loading patient state
  if (patientLoading) {
    return (
      <div className="space-y-6">
        <Link
          to={`/patients/${id}`}
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patient Record
        </Link>
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-teal-50 text-teal-600 mb-4 animate-spin">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700">Loading patient context...</p>
          <p className="text-xs text-slate-400 mt-1">Retrieving record #{id}</p>
        </div>
      </div>
    );
  }

  // 2. Patient not found state
  if (isNotFound) {
    return (
      <div className="space-y-6">
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patients Directory
        </Link>
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm max-w-2xl mx-auto">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 mx-auto flex items-center justify-center mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Patient Record Not Found</h2>
          <p className="text-sm text-slate-500 mt-2">
            Cannot upload scan. No patient record with ID <span className="font-mono font-semibold text-slate-800">#{id}</span> exists.
          </p>
          <div className="mt-6">
            <Link
              to="/"
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors shadow-sm"
            >
              Return to Patients Directory
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 3. Patient error state
  if (patientError) {
    return (
      <div className="space-y-6">
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patients Directory
        </Link>
        <div className="bg-white rounded-xl border border-rose-200 p-6 shadow-sm">
          <div className="flex items-start space-x-4">
            <div className="shrink-0 w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-rose-900">Unable to load patient</h3>
              <p className="text-xs text-rose-700 mt-1 font-mono bg-rose-50 p-2 rounded border border-rose-100">
                {patientError}
              </p>
              <button
                type="button"
                onClick={fetchPatientData}
                className="mt-3 inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-rose-700 bg-rose-100 hover:bg-rose-200 transition-colors"
              >
                Retry Connection
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 4. Main Page View
  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header & Navigation */}
      <div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-3">
          <Link to="/" className="hover:text-teal-600 transition-colors">
            Patients
          </Link>
          <span className="text-slate-300">/</span>
          <Link to={`/patients/${id}`} className="hover:text-teal-600 transition-colors">
            {patient?.name || `Patient #${id}`}
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-slate-800">Upload & Predict</span>
        </div>

        {/* Patient Context Banner */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="w-11 h-11 rounded-lg bg-teal-600 text-white flex items-center justify-center font-bold text-lg shadow-sm shrink-0">
              {patient?.name ? patient.name.charAt(0).toUpperCase() : 'P'}
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold text-slate-900">{patient?.name}</h1>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                  MRN: {patient?.mrn}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Internal Record ID: #{patient?.id} • MRI Analysis & Diagnostic Classifier
              </p>
            </div>
          </div>

          <Link
            to={`/patients/${id}`}
            className="inline-flex items-center text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 px-3 py-1.5 rounded-lg transition-colors shrink-0"
          >
            View Patient History →
          </Link>
        </div>
      </div>

      {/* Upload & Form Section (Visible when no result or when editing) */}
      {!predictionResult ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-6">
            <div>
              <h2 className="text-base font-bold text-slate-900">Upload Brain MRI Scan</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Select an axial MRI slice (JPEG/PNG) or 3D volume (NIfTI/DICOM) for neural network inference.
              </p>
            </div>

            {/* File Input Box */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">
                Scan File <span className="text-rose-500">*</span>
              </label>

              {!selectedFile ? (
                <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl p-8 hover:border-teal-500 hover:bg-teal-50/20 cursor-pointer transition-all group">
                  <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 group-hover:bg-teal-50 group-hover:text-teal-600 flex items-center justify-center mb-3 transition-colors">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-slate-700">
                    Click to browse or drag and drop MRI scan
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Supports JPG, PNG, .nii, .nii.gz, .dcm
                  </p>
                  <input
                    type="file"
                    className="hidden"
                    accept="image/jpeg,image/png,.nii,.nii.gz,.dcm"
                    onChange={handleFileChange}
                    disabled={submitting}
                  />
                </label>
              ) : (
                <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 flex flex-col md:flex-row items-center gap-6">
                  {/* Image Preview if available */}
                  {previewUrl ? (
                    <div className="relative w-40 h-40 bg-black rounded-lg overflow-hidden border border-slate-300 shrink-0 shadow-inner flex items-center justify-center">
                      <img
                        src={previewUrl}
                        alt="Scan preview"
                        className="w-full h-full object-contain"
                      />
                      <span className="absolute bottom-1 right-1 bg-black/75 text-[10px] text-white px-1.5 py-0.5 rounded font-mono">
                        Preview
                      </span>
                    </div>
                  ) : (
                    <div className="w-40 h-40 bg-slate-200 text-slate-500 rounded-lg border border-slate-300 shrink-0 flex flex-col items-center justify-center p-3 text-center">
                      <svg className="w-8 h-8 mb-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="text-xs font-semibold text-slate-700 uppercase">
                        {selectedFile.name.split('.').pop()} Volume
                      </span>
                      <span className="text-[10px] text-slate-400 mt-1">No 2D image preview</span>
                    </div>
                  )}

                  {/* File Metadata */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-teal-100 text-teal-800 font-semibold uppercase">
                        {selectedFile.name.split('.').pop()}
                      </span>
                      <h3 className="text-sm font-semibold text-slate-900 truncate">
                        {selectedFile.name}
                      </h3>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for analysis
                    </p>

                    <div className="mt-4 flex items-center gap-3">
                      <label className="text-xs font-medium text-teal-700 hover:text-teal-800 cursor-pointer underline">
                        Replace File
                        <input
                          type="file"
                          className="hidden"
                          accept="image/jpeg,image/png,.nii,.nii.gz,.dcm"
                          onChange={handleFileChange}
                          disabled={submitting}
                        />
                      </label>
                      <span className="text-slate-300">•</span>
                      <button
                        type="button"
                        onClick={clearSelectedFile}
                        disabled={submitting}
                        className="text-xs font-medium text-rose-600 hover:text-rose-800 transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Disease Model Selector */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">
                Select Diagnostic Classifier <span className="text-rose-500">*</span>
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {DISEASE_OPTIONS.map((opt) => {
                  const isSelected = diseaseType === opt.value;
                  return (
                    <div
                      key={opt.value}
                      onClick={() => !submitting && setDiseaseType(opt.value)}
                      className={`border rounded-xl p-4 cursor-pointer transition-all ${
                        isSelected
                          ? 'border-teal-600 bg-teal-50/40 ring-1 ring-teal-600'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="text-sm font-bold text-slate-900">{opt.label}</h4>
                          <p className="text-xs text-slate-500 mt-1">{opt.description}</p>
                        </div>
                        <div
                          className={`w-4 h-4 rounded-full border flex items-center justify-center mt-0.5 ${
                            isSelected ? 'border-teal-600 bg-teal-600' : 'border-slate-300'
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Advanced Tuning Parameters Collapsible */}
            <div className="border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
              >
                <svg
                  className={`w-3.5 h-3.5 mr-1.5 transition-transform duration-200 ${
                    showAdvanced ? 'rotate-90' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {showAdvanced ? 'Hide Advanced Options' : 'Show Advanced Tuning Parameters'}
              </button>

              {showAdvanced && (
                <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-4">
                  <div className="text-xs text-slate-500">
                    Optional tuning parameters for volumetric extraction and Grad-CAM spatial filtering.
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-700 mb-1">
                        Slice Index (NIfTI / DICOM)
                      </label>
                      <input
                        type="number"
                        min="0"
                        placeholder="Middle slice (auto)"
                        value={sliceIndex}
                        onChange={(e) => setSliceIndex(e.target.value)}
                        className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 font-mono"
                      />
                      <span className="text-[10px] text-slate-400 mt-1 block">
                        Ignored for 2D JPG/PNG
                      </span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-slate-700 mb-1">
                        Brightness Threshold (Grad-CAM)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={brightnessThreshold}
                        onChange={(e) => setBrightnessThreshold(e.target.value)}
                        className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 font-mono"
                      />
                      <span className="text-[10px] text-slate-400 mt-1 block">
                        Default 0.15 (masks background noise)
                      </span>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-slate-700 mb-1">
                        Boundary Erosion Pixels
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        value={erosionPixels}
                        onChange={(e) => setErosionPixels(e.target.value)}
                        className="w-full text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 font-mono"
                      />
                      <span className="text-[10px] text-slate-400 mt-1 block">
                        Default 12px (excludes scalp edges)
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Form Error Banner */}
            {submitError && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start space-x-3">
                <svg className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="flex-1 text-xs">
                  <h4 className="font-semibold text-rose-900">Analysis Request Failed</h4>
                  <p className="text-rose-700 mt-0.5 font-mono">{submitError}</p>
                </div>
              </div>
            )}

            {/* Action Bar */}
            <div className="flex items-center justify-end pt-2">
              <button
                type="submit"
                disabled={!selectedFile || !diseaseType || submitting}
                className={`inline-flex items-center px-6 py-2.5 rounded-lg text-sm font-medium text-white shadow-sm transition-all ${
                  !selectedFile || !diseaseType || submitting
                    ? 'bg-slate-300 cursor-not-allowed text-slate-500'
                    : 'bg-teal-600 hover:bg-teal-700 active:bg-teal-800'
                }`}
              >
                {submitting ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2.5 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Running Neural Inference...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Run Analysis
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      ) : (
        /* Results Section */
        <div className="space-y-6">
          {/* Primary Result Banner */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 pb-6 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
                    Classification Result
                  </span>
                  <span className="text-xs text-slate-300">•</span>
                  <span className="text-xs font-medium text-slate-500 capitalize">
                    {predictionResult.disease_type?.replace('_', ' ')}
                  </span>
                </div>

                <div className="flex items-center gap-3 mt-2 flex-wrap">
                  <span
                    className={`inline-flex items-center px-3.5 py-1 rounded-full text-base font-bold tracking-tight ${
                      isNegativeClass(predictionResult.disease)
                        ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                        : 'bg-amber-100 text-amber-900 border border-amber-300'
                    }`}
                  >
                    {formatClassLabel(predictionResult.disease)}
                  </span>

                  <span className="text-sm text-slate-500 font-medium">
                    Confidence:{' '}
                    <span className="font-bold text-slate-900">
                      {(predictionResult.confidence * 100).toFixed(1)}%
                    </span>
                  </span>

                  {predictionResult.affected_region && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                      Localization: {predictionResult.affected_region}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleReset}
                  className="inline-flex items-center px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
                >
                  <svg className="w-3.5 h-3.5 mr-1.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Run Another Scan
                </button>

                <Link
                  to={`/patients/${id}`}
                  className="inline-flex items-center px-4 py-2 text-xs font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors shadow-sm"
                >
                  View in Patient Record →
                </Link>
              </div>
            </div>

            {/* Class Probability Distribution */}
            <div className="pt-6">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">
                Full Softmax Probability Distribution
              </h3>
              <div className="space-y-3">
                {sortedProbabilities.map((item) => {
                  const isTop = item.className === predictionResult.disease;
                  return (
                    <div key={item.className} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className={`font-medium ${isTop ? 'text-slate-900 font-bold' : 'text-slate-600'}`}>
                          {formatClassLabel(item.className)} {isTop && ' (Predicted)'}
                        </span>
                        <span className="font-mono text-slate-700">{item.percentage}%</span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isTop
                              ? isNegativeClass(item.className)
                                ? 'bg-emerald-500'
                                : 'bg-teal-600'
                              : 'bg-slate-300'
                          }`}
                          style={{ width: `${Math.max(Number(item.percentage), 1)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Visual Analysis / Grad-CAM Comparison */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="mb-4">
              <h3 className="text-base font-bold text-slate-900">Spatial Attention & Heatmap</h3>
              <p className="text-xs text-slate-500">
                Visualizing convolutional layer activation with Grad-CAM localization.
              </p>
            </div>

            {predictionResult.heatmap_url ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Original Slice */}
                <div className="border border-slate-200 rounded-xl overflow-hidden bg-black p-4 flex flex-col items-center">
                  <span className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-wider">
                    Uploaded Scan Slice
                  </span>
                  <div className="w-full max-w-sm aspect-square bg-black rounded-lg overflow-hidden flex items-center justify-center">
                    {previewUrl ? (
                      <img
                        src={previewUrl}
                        alt="Uploaded MRI Slice"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="text-center text-slate-500 text-xs p-4">
                        Original scan volume uploaded ({selectedFile?.name})
                      </div>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-400 mt-2">
                    Input MRI structural slice
                  </span>
                </div>

                {/* Grad-CAM Heatmap */}
                <div className="border border-slate-200 rounded-xl overflow-hidden bg-black p-4 flex flex-col items-center">
                  <span className="text-xs font-semibold text-teal-400 mb-3 uppercase tracking-wider flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
                    Grad-CAM Activation Overlay
                  </span>
                  <div className="w-full max-w-sm aspect-square bg-black rounded-lg overflow-hidden flex items-center justify-center">
                    <img
                      src={`${apiBaseUrl}/data/${predictionResult.heatmap_url}`}
                      alt="Grad-CAM Activation Heatmap"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <div className="text-[11px] text-slate-300 mt-2 text-center">
                    Concentration indicates regions influencing {formatClassLabel(predictionResult.disease)} classification
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 rounded-xl bg-slate-50 border border-slate-200 text-center">
                <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 mx-auto flex items-center justify-center mb-3">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h4 className="text-sm font-semibold text-slate-800">No Heatmap Generated</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                  Predicted class is <span className="font-semibold text-emerald-700">{formatClassLabel(predictionResult.disease)}</span> (the baseline/negative class for this disease classifier). Grad-CAM overlays are only computed for pathological classes.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
