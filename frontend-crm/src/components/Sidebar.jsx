import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Users, Upload, FileText, LogOut, ChevronRight, FileCheck2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import clsx from "clsx";
import { toast } from "sonner";

const NAV = [
    { to: "/dashboard", icon: LayoutDashboard, label: "Tableau de bord" },
    { to: "/suppliers", icon: Users, label: "Fournisseurs" },
    { to: "/upload", icon: Upload, label: "Importer" },
    { to: "/documents", icon: FileText, label: "Documents" },
];

export default function Sidebar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        await logout();
        toast.success("Déconnecté");
        navigate("/login");
    };

    return (
        <aside className="w-64 bg-gray-900 text-white flex flex-col shrink-0">
            <div className="px-6 py-5 border-b border-gray-800">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                        <FileCheck2 size={18} className="text-white" />
                    </div>
                    <div>
                        <p className="font-bold text-sm leading-tight">
                            DocPlatform
                        </p>
                        <p className="text-xs text-gray-400 leading-tight">
                            CRM
                        </p>
                    </div>
                </div>
            </div>
            <nav className="flex-1 px-3 py-4 space-y-1">
                {NAV.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                            clsx(
                                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group",
                                isActive
                                    ? "bg-primary-600 text-white"
                                    : "text-gray-400 hover:bg-gray-800 hover:text-white",
                            )
                        }
                    >
                        <Icon size={18} />
                        <span className="flex-1">{label}</span>
                        <ChevronRight
                            size={14}
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                        />
                    </NavLink>
                ))}
            </nav>
            <div className="px-3 py-4 border-t border-gray-800">
                <div className="px-3 py-2 mb-2">
                    <p className="text-sm font-medium text-white truncate">{user?.full_name || user?.username}</p>
                    <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
                </div>
                <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                     text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
                >
                    <LogOut size={18} />
                    Déconnexion
                </button>
            </div>
        </aside>
    );
}
