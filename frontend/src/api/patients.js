import client from './client';

export const getPatients = async () => {
  const response = await client.get('/patients');
  return response.data;
};

export const createPatient = async (payload) => {
  const response = await client.post('/patients', payload);
  return response.data;
};

export const getPatient = async (id) => {
  const response = await client.get(`/patients/${id}`);
  return response.data;
};
