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
import { Spinner } from "@/components/ui/spinner";

function Guard({ children }) {
    const { user, loading } = useAuth();
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Spinner />
            </div>
        );
    }
    return user ? children : <Navigate to="/login" replace />;
}

function OperatorRoute({ children }) {
    const { canUpload } = usePermissions();
    if (!canUpload)
        return (
			<Navigate to="/dashboard" replace />
        );
    return children;
}

export default function App() {
    return (
        <BrowserRouter future={{ v7_startTransition: true }}>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route
                    path="/"
                    element={
                        <Guard>
                            <Layout />
                        </Guard>
                    }
                >
                    <Route
                        index
                        element={<Navigate to="/dashboard" replace />}
                    />
                    <Route path="dashboard" element={<Dashboard />} />
                    <Route path="suppliers" element={<Suppliers />} />
                    <Route path="suppliers/:id" element={<SupplierDetail />} />
                    <Route
                        path="upload"
                        element={
                            <OperatorRoute>
                                <Upload />
                            </OperatorRoute>
                        }
                    />
                    <Route path="documents" element={<Documents />} />
                    <Route path="documents/:id" element={<DocumentDetail />} />
                </Route>
                <Route
                    path="*"
                    element={<Navigate to="/dashboard" replace />}
                />
            </Routes>
        </BrowserRouter>
    );
}
