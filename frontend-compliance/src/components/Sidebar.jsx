import { NavLink, useNavigate } from "react-router-dom";
import {
    LayoutDashboard,
    AlertTriangle,
    Calendar,
    Users,
    LogOut,
    Shield,
    ChevronRight,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { statsApi } from "../api/index";
import clsx from "clsx";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "./ui/badge";

const NAV = [
    { to: "/dashboard", icon: LayoutDashboard, label: "Tableau de bord" },
    {
        to: "/anomalies",
        icon: AlertTriangle,
        label: "Anomalies",
        badge: "unresolved_anomalies",
    },
    {
        to: "/expirations",
        icon: Calendar,
        label: "Expirations",
        badge: "documents_expiring_soon",
    },
    { to: "/suppliers", icon: Users, label: "Fournisseurs" },
];

export default function Sidebar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const { data: stats } = useQuery({
        queryKey: ["stats"],
        queryFn: statsApi.dashboard,
        refetchInterval: 30_000,
    });

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <aside className="w-64 bg-sidebar text-sidebar-foreground flex flex-col shrink-0">
            <div className="px-6 py-5 border-b border-sidebar-border">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-background rounded-lg flex items-center justify-center">
                        <Shield size={18} className="text-primary" />
                    </div>
                    <div>
                        <p className="font-prata font-bold text-sm leading-tight">
                            DocPlatform
                        </p>
                        <p className="text-xs text-sidebar-foreground/70 leading-tight">
                            Conformité
                        </p>
                    </div>
                </div>
            </div>

            <nav className="flex-1 px-3 py-4 space-y-1">
                {NAV.map(({ to, icon: Icon, label, badge }) => {
                    const count = badge && stats?.[badge];
                    return (
                        <NavLink
                            key={to}
                            to={to}
                            className={({ isActive }) =>
                                clsx(
                                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group",
                                    isActive
                                        ? "bg-sidebar-primary text-sidebar-primary-foreground"
                                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                                )
                            }
                        >
                            <Icon size={18} />
                            <span className="flex-1">{label}</span>
                            {count > 0 && (
                                <Badge variant="destructive">
                                    {count > 99 ? "99+" : count}
                                </Badge>
                            )}
                            <ChevronRight
                                size={14}
                                className="opacity-0 group-hover:opacity-100 transition-opacity"
                            />
                        </NavLink>
                    );
                })}
            </nav>

            <div className="px-3 py-4 border-t border-sidebar-border">
                <div className="px-3 py-2 mb-2">
                    <p className="text-sm font-medium text-sidebar-foreground truncate">
                        {user?.full_name || user?.username}
                    </p>
                    <p className="text-xs text-sidebar-foreground/70 capitalize">
                        {user?.role}
                    </p>
                </div>
                <Button
                    variant="ghost"
                    onClick={handleLogout}
                    className="justify-start w-full text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                >
                    <LogOut size={18} /> Déconnexion
                </Button>
            </div>
        </aside>
    );
}
