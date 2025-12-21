import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from './pages/Login';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { TeacherClassDetail } from './pages/TeacherClassDetail';
import { TeacherHomework } from './pages/TeacherHomework';
import { StudentDashboard } from './pages/StudentDashboard';
import { MainLayout } from './components/Layout';
import { useStore } from './store/useStore';
import { Role } from './types';

// Protected Route Wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode, allowedRoles?: Role[] }> = ({ children, allowedRoles }) => {
  const { isAuthenticated, user } = useStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/login" replace />; // Or forbidden page
  }

  return <MainLayout>{children}</MainLayout>;
};

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        {/* Teacher Routes */}
        <Route 
          path="/teacher/dashboard" 
          element={
            <ProtectedRoute allowedRoles={[Role.Teacher]}>
              <TeacherDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/teacher/class/:id" 
          element={
            <ProtectedRoute allowedRoles={[Role.Teacher]}>
              <TeacherClassDetail />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/teacher/homework" 
          element={
            <ProtectedRoute allowedRoles={[Role.Teacher]}>
              <TeacherHomework />
            </ProtectedRoute>
          } 
        />

        {/* Student Routes */}
        <Route 
          path="/student/dashboard" 
          element={
            <ProtectedRoute allowedRoles={[Role.Student]}>
              <StudentDashboard />
            </ProtectedRoute>
          } 
        />

        {/* Default Redirect */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
  );
};

export default App;