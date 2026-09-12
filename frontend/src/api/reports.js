import client from './client';

export const getPatientReports = async (patientId) => {
  const response = await client.get(`/patients/${patientId}/reports`);
  return response.data;
};

export const generateReport = async (patientId) => {
  const response = await client.post(`/patients/${patientId}/report`, null, {
    timeout: 60000,
  });
  return response.data;
};
