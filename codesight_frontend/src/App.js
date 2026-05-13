import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Sidebar from './components/layout/Sidebar';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ProjectsPage from './pages/ProjectsPage';
import AddProjectPage from './pages/AddProjectPage';
import BuildStatusPage from './pages/BuildStatusPage';
import ReportPage from './pages/ReportPage';
import SecurityPage from './pages/SecurityPage';
import ArchPage from './pages/ArchPage';
import DetailPage from './pages/DetailPage';

function ProtectedLayout() {
  return (
    <div className="layout">
      <Sidebar />
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        Загрузка...
      </div>
    );
  }
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <PrivateRoute>
            <ProtectedLayout />
          </PrivateRoute>
        }
      >
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/add" element={<AddProjectPage />} />
        <Route path="/projects/:id" element={<DetailPage />} />
        <Route path="/projects/:id/status" element={<BuildStatusPage />} />
        <Route path="/projects/:id/report" element={<ReportPage />} />
        <Route path="/projects/:id/security" element={<SecurityPage />} />
        <Route path="/projects/:id/architecture" element={<ArchPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
