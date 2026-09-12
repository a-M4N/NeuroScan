import client from './client';

export const getPatientScans = async (patientId) => {
  const response = await client.get(`/patients/${patientId}/scans`);
  return response.data;
};
