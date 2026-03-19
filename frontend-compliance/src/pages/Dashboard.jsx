import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
    AlertTriangle,
    XCircle,
    CheckCircle,
    Calendar,
    ShieldAlert,
} from "lucide-react";
import { statsApi, anomaliesApi, suppliersApi } from "@/api/index";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const COMPLIANCE_COLORS = {
    compliant: "var(--primary)",
    warning: "var(--chart-2)",
    non_compliant: "var(--destructive)",
    pending: "var(--muted-foreground)",
};

function StatCard({ icon: Icon, label, value, sub, color = "blue", loading }) {
    const colors = {
        blue: "bg-primary/10 text-primary",
        green: "bg-primary/10 text-primary",
        yellow: "bg-chart-2/10 text-chart-2",
        red: "bg-destructive/10 text-destructive",
        purple: "bg-chart-3/10 text-chart-3",
        orange: "bg-chart-3/10 text-chart-3",
    };
    return (
        <Card className="py-4 gap-0 shadow-none">
            <CardContent className="px-4 flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${colors[color]}`}>
                    <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground font-medium">{label}</p>
                    {loading ? (
                        <div className="h-7 w-16 bg-muted rounded-sm animate-pulse mt-1" />
                    ) : (
                        <div className="flex gap-1 items-baseline">
                            <p className="text-2xl font-bold text-foreground">
                                {value ?? "—"}
                            </p>
                            {sub && (
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {sub}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

function SeverityBadge({ severity }) {
    const cfg =
        {
            error: "bg-destructive/15 text-destructive",
            warning: "bg-chart-2/15 text-chart-2",
            info: "bg-primary/15 text-primary",
        }[severity] || "bg-muted text-muted-foreground";
    return (
        <span
            className={`inline-flex text-xs font-medium px-2 py-0.5 rounded-full ${cfg}`}
        >
            {severity}
        </span>
    );
}

export default function Dashboard() {
    const { data: stats, isLoading } = useQuery({
        queryKey: ["stats"],
        queryFn: statsApi.dashboard,
        refetchInterval: 15_000,
    });
    const { data: recentAnomalies = [] } = useQuery({
        queryKey: ["anomalies", { resolved: false, limit: 8 }],
        queryFn: () => anomaliesApi.list({ resolved: false, limit: 8 }),
    });
    const { data: suppliers = [] } = useQuery({
        queryKey: ["suppliers"],
        queryFn: () => suppliersApi.list({ limit: 100 }),
    });

    const complianceCounts = suppliers.reduce((acc, s) => {
        acc[s.compliance_status] = (acc[s.compliance_status] || 0) + 1;
        return acc;
    }, {});
    const pieData = Object.entries(complianceCounts).map(([name, value]) => ({
        name,
        value,
    }));

    const complianceRate =
        suppliers.length > 0
            ? Math.round(
                  ((complianceCounts.compliant || 0) / suppliers.length) * 100,
              )
            : 0;

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="font-prata text-2xl font-bold text-foreground">
                        Tableau de bord
                    </h1>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Vue d'ensemble des risques et anomalies
                    </p>
                </div>
                <div className="flex items-center gap-2 bg-card border border-border rounded-xl px-4 py-2">
                    <div
                        className={`w-2.5 h-2.5 rounded-full ${complianceRate >= 80 ? "bg-primary" : complianceRate >= 50 ? "bg-chart-2" : "bg-destructive"}`}
                    />
                    <span className="text-sm font-semibold text-foreground">
                        {complianceRate}% conformes
                    </span>
                </div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <StatCard
                    icon={XCircle}
                    label="Anomalies critiques"
                    value={stats?.critical_anomalies}
                    color="red"
                    loading={isLoading}
                    sub="erreurs bloquantes"
                />
                <StatCard
                    icon={AlertTriangle}
                    label="Non résolues"
                    value={stats?.unresolved_anomalies}
                    color="orange"
                    loading={isLoading}
                />
                <StatCard
                    icon={Calendar}
                    label="Expire bientôt"
                    value={stats?.documents_expiring_soon}
                    color="orange"
                    loading={isLoading}
                    sub="< 30 jours"
                />
                <StatCard
                    icon={CheckCircle}
                    label="Fournisseurs conformes"
                    value={complianceCounts.compliant || 0}
                    color="green"
                    loading={isLoading}
                    sub={`sur ${suppliers.length}`}
                />
            </div>

            <div className="grid grid-cols-3 gap-6">
                <div className="col-span-2 card">
                    <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                        <h2 className="font-semibold text-foreground flex items-center gap-2">
                            <ShieldAlert
                                size={16}
                                className="text-chart-3"
                            />
                            Anomalies non résolues
                        </h2>
                        <Button variant="secondary" asChild>
                            <Link to="/documents">Voir tout</Link>
                        </Button>
                    </div>
                    {recentAnomalies.length === 0 ? (
                        <div className="px-6 py-12 text-center">
                            <CheckCircle
                                size={36}
                                className="mx-auto text-primary mb-3"
                            />
                            <p className="text-sm text-muted-foreground">
                                Aucune anomalie non résolue
                            </p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border">
                            {recentAnomalies.map((a) => (
                                <div
                                    key={a.anomaly_id}
                                    className="px-6 py-3.5 flex items-start gap-3"
                                >
                                    <SeverityBadge severity={a.severity} />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-foreground truncate">
                                            {a.message}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            {a.supplier_name && (
                                                <span className="font-medium">
                                                    {a.supplier_name} ·{" "}
                                                </span>
                                            )}
                                            {formatDistanceToNow(
                                                new Date(a.detected_at),
                                                { addSuffix: true, locale: fr },
                                            )}
                                        </p>
                                    </div>
                                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                                        {a.type.replace("_", " ")}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
                <div className="card p-5">
                    <h2 className="font-semibold text-foreground mb-4">
                        Conformité fournisseurs
                    </h2>
                    {suppliers.length === 0 ? (
                        <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
                            Aucun fournisseur
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={55}
                                    outerRadius={80}
                                    paddingAngle={3}
                                    dataKey="value"
                                >
                                    {pieData.map((entry) => (
                                        <Cell
                                            key={entry.name}
                                            fill={
                                                COMPLIANCE_COLORS[entry.name] ||
                                                "#94a3b8"
                                            }
                                        />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(v, n) => [v, n]} />
                                <Legend
                                    iconType="circle"
                                    iconSize={8}
                                    formatter={(v) => (
                                        <span className="text-xs text-muted-foreground capitalize">
                                            {v}
                                        </span>
                                    )}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    )}
                    <div className="mt-2 space-y-1.5">
                        {Object.entries(complianceCounts).map(
                            ([status, count]) => (
                                <div
                                    key={status}
                                    className="flex items-center justify-between text-xs"
                                >
                                    <div className="flex items-center gap-2">
                                        <div
                                            className="w-2 h-2 rounded-full"
                                            style={{
                                                background:
                                                    COMPLIANCE_COLORS[status] ||
                                                    "var(--muted-foreground)",
                                            }}
                                        />
                                        <span className="text-muted-foreground capitalize">
                                            {status.replace("_", " ")}
                                        </span>
                                    </div>
                                    <span className="font-semibold text-foreground">
                                        {count}
                                    </span>
                                </div>
                            ),
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
