import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Anomalies from "./pages/Anomalies";
import Expirations from "./pages/Expirations";
import Suppliers from "./pages/Suppliers";
import SupplierCompliance from "./pages/SupplierCompliance";
import { Spinner } from "@/components/ui/spinner"

function Guard({ children }) {
    const { user, loading } = useAuth();
    if (loading)
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Spinner />
            </div>
        );
    return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
    return (
        <BrowserRouter future={{ v7_startTransition: true }}>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Guard><Layout /></Guard>}>
                    <Route index element={<Navigate to="/dashboard" replace />} />
                    <Route path="dashboard" element={<Dashboard />} />
                    <Route path="anomalies" element={<Anomalies />} />
                    <Route path="expirations" element={<Expirations />} />
                    <Route path="suppliers" element={<Suppliers />} />
                    <Route path="suppliers/:id" element={<SupplierCompliance />} />
                </Route>
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
        </BrowserRouter>
    );
}
