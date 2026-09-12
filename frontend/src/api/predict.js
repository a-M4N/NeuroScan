import client from './client';

export const predictScan = async (formData) => {
  const response = await client.post('/predict', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 60000,
  });
  return response.data;
};
