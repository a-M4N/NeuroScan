import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import PatientsList from './pages/PatientsList';
import PatientDetail from './pages/PatientDetail';
import PredictScan from './pages/PredictScan';

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Layout>
            <PatientsList />
          </Layout>
        }
      />
      <Route
        path="/patients/:id"
        element={
          <Layout>
            <PatientDetail />
          </Layout>
        }
      />
      <Route
        path="/patients/:id/upload"
        element={
          <Layout>
            <PredictScan />
          </Layout>
        }
      />
    </Routes>
  );
}
