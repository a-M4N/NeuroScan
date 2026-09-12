import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPatient } from '../api/patients';
import { getPatientReports, generateReport } from '../api/reports';
import { getPatientScans } from '../api/scans';

export default function PatientDetail() {
  const { id } = useParams();
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  // 1. Patient state
  const [patient, setPatient] = useState(null);
  const [patientLoading, setPatientLoading] = useState(true);
  const [patientError, setPatientError] = useState(null);
  const [isNotFound, setIsNotFound] = useState(false);

  // 2. Reports state
  const [reports, setReports] = useState([]);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [reportsError, setReportsError] = useState(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [generateError, setGenerateError] = useState(null);
  const [justGeneratedId, setJustGeneratedId] = useState(null);

  // 3. Scans state
  const [scans, setScans] = useState([]);
  const [scansLoading, setScansLoading] = useState(true);
  const [scansError, setScansError] = useState(null);

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

  // Fetch Reports
  const fetchReportsData = useCallback(async () => {
    try {
      setReportsLoading(true);
      setReportsError(null);
      const data = await getPatientReports(id);
      setReports(Array.isArray(data) ? data : []);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to load reports history.';
      setReportsError(msg);
    } finally {
      setReportsLoading(false);
    }
  }, [id]);

  // Trigger Report Generation
  const handleGenerateReport = async () => {
    if (generatingReport) return;
    try {
      setGeneratingReport(true);
      setGenerateError(null);
      setJustGeneratedId(null);
      const newReport = await generateReport(id);
      await fetchReportsData();
      if (newReport?.id) {
        setJustGeneratedId(newReport.id);
      }
    } catch (err) {
      const serverDetail = err.response?.data?.detail;
      let readableError;
      if (typeof serverDetail === 'string') {
        readableError = serverDetail;
      } else if (Array.isArray(serverDetail) && serverDetail.length > 0) {
        readableError = serverDetail.map((d) => d.msg || JSON.stringify(d)).join(', ');
      } else {
        readableError = err.message || 'Failed to generate diagnostic report.';
      }
      setGenerateError(readableError);
    } finally {
      setGeneratingReport(false);
    }
  };

  // Fetch Scans
  const fetchScansData = useCallback(async () => {
    try {
      setScansLoading(true);
      setScansError(null);
      const data = await getPatientScans(id);
      setScans(Array.isArray(data) ? data : []);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to load imaging scans.';
      setScansError(msg);
    } finally {
      setScansLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchPatientData();
    fetchReportsData();
    fetchScansData();
  }, [fetchPatientData, fetchReportsData, fetchScansData]);

  // Date formatting helpers
  const formatDateOnly = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '—';
      return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        timeZone: 'UTC',
      }).format(date);
    } catch {
      return '—';
    }
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return '—';
      return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date);
    } catch {
      return '—';
    }
  };

  // Case A: Page-level Loading
  if (patientLoading) {
    return (
      <div className="space-y-6">
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patients
        </Link>
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-teal-50 text-teal-600 mb-4 animate-spin">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
          </div>
          <p className="text-sm font-medium text-slate-700">Loading patient details...</p>
          <p className="text-xs text-slate-400 mt-1">Retrieving record #{id}</p>
        </div>
      </div>
    );
  }

  // Case B: Distinct Patient Not Found (404)
  if (isNotFound) {
    return (
      <div className="space-y-6">
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patients
        </Link>
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm max-w-2xl mx-auto">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 mx-auto flex items-center justify-center mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Patient Record Not Found</h2>
          <p className="text-sm text-slate-500 mt-2">
            No patient record with ID <span className="font-mono font-semibold text-slate-800">#{id}</span> exists in the NeuroScan database.
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

  // Case C: Page-level General Error
  if (patientError) {
    return (
      <div className="space-y-6">
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          ← Back to Patients
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

  // Case D: Populated Page
  return (
    <div className="space-y-8">
      {/* Navigation & Header */}
      <div>
        <Link
          to="/"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-teal-600 transition-colors mb-3"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Patients Directory
        </Link>

        {/* Patient Identity Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="flex items-start space-x-4">
              <div className="w-14 h-14 rounded-xl bg-teal-600 text-white flex items-center justify-center font-bold text-2xl shadow-sm shrink-0">
                {patient?.name ? patient.name.charAt(0).toUpperCase() : 'P'}
              </div>
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                    {patient?.name || '—'}
                  </h1>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                    MRN: {patient?.mrn || '—'}
                  </span>
                </div>
                <div className="flex items-center gap-6 mt-2 text-xs text-slate-500 flex-wrap">
                  <div>
                    <span className="text-slate-400">Date of Birth: </span>
                    <span className="font-medium text-slate-700">
                      {formatDateOnly(patient?.date_of_birth)}
                    </span>
                  </div>
                  <span className="text-slate-300">•</span>
                  <div>
                    <span className="text-slate-400">Registered: </span>
                    <span className="font-medium text-slate-700">
                      {formatDateTime(patient?.created_at)}
                    </span>
                  </div>
                  <span className="text-slate-300">•</span>
                  <div>
                    <span className="text-slate-400">Internal ID: </span>
                    <span className="font-mono text-slate-600">#{patient?.id}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Upload Scan Button */}
            <div>
              <Link
                to={`/patients/${id}/upload`}
                className="inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 active:bg-teal-800 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 shrink-0"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Upload Scan
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Reports Section */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Diagnostic Reports</h2>
            <p className="text-xs text-slate-500">
              Generated clinical syntheses and compiled PDF documentation
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">
              {reports.length} report{reports.length === 1 ? '' : 's'}
            </span>
            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className={`inline-flex items-center justify-center px-3.5 py-1.5 text-xs font-medium rounded-lg shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 shrink-0 ${
                generatingReport
                  ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                  : 'text-white bg-teal-600 hover:bg-teal-700 active:bg-teal-800'
              }`}
            >
              {generatingReport ? (
                <>
                  <svg className="animate-spin -ml-0.5 mr-2 h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Synthesizing Report...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Generate Report
                </>
              )}
            </button>
          </div>
        </div>

        {/* Report Generation Progress Banner */}
        {generatingReport && (
          <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 text-xs text-teal-800 flex items-start space-x-3 shadow-sm animate-pulse">
            <svg className="w-4 h-4 text-teal-600 shrink-0 mt-0.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <div>
              <p className="font-semibold text-teal-900">Generating diagnostic report...</p>
              <p className="text-teal-700 mt-0.5">
                Gemini LLM is synthesizing longitudinal clinical findings and compiling the WeasyPrint PDF. This typically takes 10–25 seconds.
              </p>
            </div>
          </div>
        )}

        {/* Report Generation Error Alert */}
        {generateError && (
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-800 flex items-start justify-between shadow-sm">
            <div className="flex items-start space-x-2.5">
              <svg className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="font-semibold text-rose-900">Failed to generate report</p>
                <p className="text-rose-700 mt-0.5 font-mono">{generateError}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setGenerateError(null)}
              className="text-rose-500 hover:text-rose-700 text-xs font-semibold ml-3"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Report Generation Success Toast */}
        {justGeneratedId && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 text-xs text-emerald-800 flex items-center justify-between shadow-sm">
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>
                Report <strong className="font-mono font-semibold">#{justGeneratedId}</strong> successfully generated and compiled into PDF.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setJustGeneratedId(null)}
              className="text-emerald-600 hover:text-emerald-800 font-semibold text-xs"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Reports Loading */}
        {reportsLoading && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
            <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-teal-50 text-teal-600 mb-2 animate-spin">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            </div>
            <p className="text-xs text-slate-500">Loading diagnostic reports...</p>
          </div>
        )}

        {/* Reports Error */}
        {!reportsLoading && reportsError && (
          <div className="bg-white rounded-xl border border-rose-200 p-4 shadow-sm text-xs">
            <div className="flex items-center justify-between">
              <span className="text-rose-800">Failed to load reports: {reportsError}</span>
              <button
                type="button"
                onClick={fetchReportsData}
                className="text-rose-700 underline font-medium hover:text-rose-900 ml-3"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Reports Empty */}
        {!reportsLoading && !reportsError && reports.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
            <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-3">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-slate-800">No reports generated yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Diagnostic reports will appear here once an MRI scan is processed and a clinical narrative is generated.
            </p>
          </div>
        )}

        {/* Reports Populated Table */}
        {!reportsLoading && !reportsError && reports.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">Report ID</th>
                  <th scope="col" className="px-6 py-3.5">Generated Date</th>
                  <th scope="col" className="px-6 py-3.5">Status / PDF</th>
                  <th scope="col" className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {reports.map((report) => {
                  const reportId = report?.id ?? '—';
                  const generatedDate = formatDateTime(report?.generated_at);
                  const pdfUrl = `${apiBaseUrl}/patients/${id}/reports/${report.id}/pdf`;

                  return (
                    <tr key={report?.id || Math.random()} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs font-semibold text-slate-800">
                        Report #{reportId}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600">
                        {generatedDate}
                      </td>
                      <td className="px-6 py-4 text-xs">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Compiled
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <a
                          href={pdfUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-xs font-medium text-teal-600 hover:text-teal-800 transition-colors"
                        >
                          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          View PDF
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Scans Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Imaging Scans</h2>
            <p className="text-xs text-slate-500">
              Processed volumetric or slice imaging records and model inferences
            </p>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {scans.length} scan{scans.length === 1 ? '' : 's'}
          </span>
        </div>

        {/* Scans Loading */}
        {scansLoading && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
            <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-teal-50 text-teal-600 mb-2 animate-spin">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            </div>
            <p className="text-xs text-slate-500">Loading scan history...</p>
          </div>
        )}

        {/* Scans Error */}
        {!scansLoading && scansError && (
          <div className="bg-white rounded-xl border border-rose-200 p-4 shadow-sm text-xs">
            <div className="flex items-center justify-between">
              <span className="text-rose-800">Failed to load scans: {scansError}</span>
              <button
                type="button"
                onClick={fetchScansData}
                className="text-rose-700 underline font-medium hover:text-rose-900 ml-3"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Scans Empty */}
        {!scansLoading && !scansError && scans.length === 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-sm">
            <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-3">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-slate-800">No scans uploaded yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Upload a brain MRI scan (JPG, PNG, NIfTI, or DICOM) to begin running classification and heatmaps.
            </p>
          </div>
        )}

        {/* Scans Populated Table */}
        {!scansLoading && !scansError && scans.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">Scan ID</th>
                  <th scope="col" className="px-6 py-3.5">Upload Date</th>
                  <th scope="col" className="px-6 py-3.5">Modality</th>
                  <th scope="col" className="px-6 py-3.5">Predictions / Diagnosis</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {scans.map((scan) => {
                  const scanId = scan?.id ?? '—';
                  const uploadDate = formatDateTime(scan?.upload_date);
                  const modality = scan?.modality?.toUpperCase() || 'MRI';
                  const predictions = scan?.predictions || [];

                  return (
                    <tr key={scan?.id || Math.random()} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs font-semibold text-slate-800">
                        #{scanId}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-600">
                        {uploadDate}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 text-slate-700">
                          {modality}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {predictions.length === 0 ? (
                          <span className="text-xs text-slate-400">No predictions evaluated</span>
                        ) : (
                          <div className="space-y-1.5">
                            {predictions.map((pred) => {
                              const confidencePct = pred?.confidence
                                ? (pred.confidence * 100).toFixed(1) + '%'
                                : '—';
                              const disease = (pred?.disease_type || '').replace('_', ' ');
                              const predictedClass = (pred?.predicted_class || '').replace('_', ' ');

                              return (
                                <div key={pred?.id || Math.random()} className="flex items-center space-x-2 text-xs">
                                  <span className="font-semibold text-slate-900 capitalize">
                                    {predictedClass}
                                  </span>
                                  <span className="text-slate-400 font-mono text-[11px]">
                                    ({confidencePct})
                                  </span>
                                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-teal-50 text-teal-700">
                                    {disease}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
