import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { usePermissions } from "@/hooks/usePermissions";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Suppliers from "@/pages/Suppliers";
import SupplierDetail from "@/pages/SupplierDetail";
import Upload from "@/pages/Upload";
import Documents from "@/pages/Documents";
import DocumentDetail from "@/pages/DocumentDetail";

function PrivateRoute({ children }) {
    const { user, loading } = useAuth();
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }
    return user ? children : <Navigate to="/login" replace />;
}

function OperatorRoute({ children }) {
  const { canUpload } = usePermissions()
  if (!canUpload) return (
    <div className="p-12 text-center">
      <p className="text-4xl mb-4">🔒</p>
      <h2 className="text-xl font-semibold text-gray-800 mb-2">Accès non autorisé</h2>
      <p className="text-gray-500 text-sm">Votre rôle ne permet pas d'accéder à cette page.</p>
      <Navigate to="/dashboard" replace />
    </div>
  )
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="suppliers" element={<Suppliers />} />
          <Route path="suppliers/:id" element={<SupplierDetail />} />
          <Route path="upload" element={<OperatorRoute><Upload /></OperatorRoute>} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:id" element={<DocumentDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
