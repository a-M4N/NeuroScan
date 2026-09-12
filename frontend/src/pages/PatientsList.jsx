import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getPatients } from '../api/patients';
import AddPatientModal from '../components/patients/AddPatientModal';

export default function PatientsList() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchPatients = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPatients();
      setPatients(Array.isArray(data) ? data : []);
    } catch (err) {
      const serverDetail = err.response?.data?.detail;
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const readableError =
        serverDetail ||
        err.message ||
        `Unable to reach backend API at ${baseUrl}. Please ensure the server is running.`;
      setError(readableError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  const handlePatientCreated = () => {
    setIsModalOpen(false);
    fetchPatients();
  };

  const formatDate = (dateStr) => {
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Patients
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Clinical neuro-imaging records and brain MRI diagnostics.
          </p>
        </div>

        {/* Add Patient Button */}
        <div>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 active:bg-teal-800 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
          >
            <svg
              className="w-4 h-4 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            Add Patient
          </button>
        </div>
      </div>

      {/* State 1: Loading State */}
      {loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-teal-50 text-teal-600 mb-4 animate-spin">
            <svg
              className="w-6 h-6"
              fill="none"
              viewBox="0 0 24 24"
            >
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
          <p className="text-sm font-medium text-slate-700">Loading patients records...</p>
          <p className="text-xs text-slate-400 mt-1">Contacting NeuroScan database</p>
        </div>
      )}

      {/* State 2: Error State */}
      {!loading && error && (
        <div className="bg-white rounded-xl border border-rose-200 p-6 shadow-sm">
          <div className="flex items-start space-x-4">
            <div className="shrink-0 w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-rose-900">
                Unable to load patient records
              </h3>
              <p className="text-sm text-rose-700 mt-1 font-mono text-xs bg-rose-50/50 p-2.5 rounded border border-rose-100 break-all">
                {error}
              </p>
              <div className="mt-4 flex items-center space-x-3">
                <button
                  type="button"
                  onClick={fetchPatients}
                  className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-rose-700 bg-rose-100 hover:bg-rose-200 transition-colors"
                >
                  <svg
                    className="w-3.5 h-3.5 mr-1.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* State 3: Empty State */}
      {!loading && !error && patients.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-4">
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-slate-800">No patients yet</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            Get started by adding your first patient to begin recording MRI scans and running diagnosis models.
          </p>
        </div>
      )}

      {/* State 4: Populated List / Table */}
      {!loading && !error && patients.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">
                    Patient ID
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Name
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    MRN
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Registered
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {patients.map((patient) => {
                  const patientId = patient?.id ?? '—';
                  const patientName = patient?.name ?? '—';
                  const patientMrn = patient?.mrn ?? '—';
                  const createdAt = formatDate(patient?.created_at);

                  return (
                    <tr
                      key={patient?.id || Math.random()}
                      className="hover:bg-slate-50/80 transition-colors group"
                    >
                      <td className="px-6 py-4 font-mono text-xs font-medium text-slate-600">
                        #{patientId}
                      </td>
                      <td className="px-6 py-4 font-semibold text-slate-900">
                        <Link
                          to={`/patients/${patientId}`}
                          className="hover:text-teal-600 focus:outline-none focus:underline"
                        >
                          {patientName}
                        </Link>
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs font-mono">
                        {patientMrn}
                      </td>
                      <td className="px-6 py-4 text-slate-500 text-xs">
                        {createdAt}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={`/patients/${patientId}`}
                          className="inline-flex items-center text-xs font-medium text-teal-600 hover:text-teal-800 transition-colors"
                        >
                          View Details
                          <svg
                            className="w-3.5 h-3.5 ml-1 transition-transform group-hover:translate-x-0.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 5l7 7-7 7"
                            />
                          </svg>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Patient Modal Form */}
      <AddPatientModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onPatientCreated={handlePatientCreated}
      />
    </div>
  );
}
