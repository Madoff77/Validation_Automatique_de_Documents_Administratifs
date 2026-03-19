import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
    Users,
    Search,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Clock,
    ChevronRight,
} from "lucide-react";
import { suppliersApi } from "../api/index";
import clsx from "clsx";
import {
    InputGroup,
    InputGroupAddon,
    InputGroupInput,
} from "@/components/ui/input-group";
import { ButtonGroup } from "@/components/ui/button-group";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";

const STATUS_CONFIG = {
    compliant: {
        label: "Conforme",
        icon: CheckCircle,
        color: "text-primary",
        bg: "bg-primary/15",
        border: "border-primary/30",
    },
    warning: {
        label: "Avertissement",
        icon: AlertTriangle,
        color: "text-chart-2",
        bg: "bg-chart-2/15",
        border: "border-chart-2/30",
    },
    non_compliant: {
        label: "Non conforme",
        icon: XCircle,
        color: "text-destructive",
        bg: "bg-destructive/15",
        border: "border-destructive/30",
    },
    pending: {
        label: "En attente",
        icon: Clock,
        color: "text-muted-foreground",
        bg: "bg-muted",
        border: "border-border",
    },
};

function StatusBadge({ status }) {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
    const { icon: Icon } = cfg;
    return (
        <span
            className={clsx(
                "inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full border",
                cfg.bg,
                cfg.color,
                cfg.border,
            )}
        >
            <Icon size={11} />
            {cfg.label}
        </span>
    );
}

export default function Suppliers() {
    const [search, setSearch] = useState("");
    const [filterStatus, setFilterStatus] = useState("");

    const { data: suppliers = [], isLoading } = useQuery({
        queryKey: ["suppliers"],
        queryFn: () => suppliersApi.list({ limit: 200 }),
        refetchInterval: 30_000,
    });

    const filtered = suppliers.filter((s) => {
        const matchSearch =
            !search ||
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.siret?.includes(search);
        const matchStatus =
            !filterStatus || s.compliance_status === filterStatus;
        return matchSearch && matchStatus;
    });

    const counts = suppliers.reduce((acc, s) => {
        acc[s.compliance_status] = (acc[s.compliance_status] || 0) + 1;
        return acc;
    }, {});

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="font-prata text-2xl font-bold text-foreground">
                        Fournisseurs
                    </h1>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        {suppliers.length} fournisseur
                        {suppliers.length > 1 ? "s" : ""} enregistrés
                    </p>
                </div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {Object.entries(STATUS_CONFIG).map(([status, cfg]) => {
                    const { icon: Icon } = cfg;
                    return (
                        <Button
                            key={status}
                            onClick={() =>
                                setFilterStatus(
                                    filterStatus === status ? "" : status,
                                )
                            }
                            variant={
                                filterStatus === status ? "default" : "ghost"
                            }
                            className={clsx(
                                "card p-4 h-auto justify-start items-start transition-all",
                                filterStatus === status &&
                                    `ring-2 ring-offset-1 ${cfg.border}`,
                            )}
                        >
                            <div className={clsx("p-2 rounded-lg", cfg.bg)}>
                                <Icon size={16} className={cfg.color} />
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground">
                                    {cfg.label}
                                </p>
                                <p className="text-xl font-bold text-foreground">
                                    {counts[status] || 0}
                                </p>
                            </div>
                        </Button>
                    );
                })}
            </div>
            <Field className="max-w-xs w-full">
                <ButtonGroup>
                    <InputGroup>
                        <InputGroupAddon>
                            <Search size={16} />
                        </InputGroupAddon>
                        <InputGroupInput
                            id="search"
                            placeholder="Rechercher par nom ou SIRET..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </InputGroup>
                    {(search || filterStatus) && (
                        <Button
                            onClick={() => {
                                setSearch("");
                                setFilterStatus("");
                            }}
                            variant="outline"
                        >
                            Effacer
                        </Button>
                    )}
                </ButtonGroup>
            </Field>
            {isLoading ? (
                <div className="card divide-y divide-border">
                    {[...Array(5)].map((_, i) => (
                        <div
                            key={i}
                            className="px-5 py-4 flex items-center gap-4 animate-pulse"
                        >
                            <div className="w-10 h-10 bg-muted rounded-xl" />
                            <div className="flex-1 space-y-2">
                                <div className="h-4 bg-muted rounded-xs w-1/3" />
                                <div className="h-3 bg-muted rounded-xs w-1/4" />
                            </div>
                            <div className="h-6 w-24 bg-muted rounded-full" />
                        </div>
                    ))}
                </div>
            ) : filtered.length === 0 ? (
                <div className="card py-16 text-center">
                    <Users
                        size={40}
                        className="mx-auto text-muted-foreground mb-3"
                    />
                    <p className="text-muted-foreground">
                        Aucun fournisseur trouvé
                    </p>
                </div>
            ) : (
                <div className="card divide-y divide-border">
                    {filtered.map((supplier) => (
                        <Link
                            key={supplier.supplier_id}
                            to={`/suppliers/${supplier.supplier_id}`}
                            className="flex items-center gap-4 px-5 py-4 hover:bg-muted/40 transition-colors group"
                        >
                            <div className="w-10 h-10 bg-muted rounded-xl flex items-center justify-center text-muted-foreground font-semibold text-sm shrink-0 group-hover:bg-primary/15 group-hover:text-primary transition-colors">
                                {supplier.name.slice(0, 2).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-semibold text-foreground truncate">
                                    {supplier.name}
                                </p>
                                <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                                    {supplier.siret && (
                                        <span className="font-mono">
                                            {supplier.siret}
                                        </span>
                                    )}
                                    {supplier.contact_email && (
                                        <span>{supplier.contact_email}</span>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                                {supplier.active_anomalies_count > 0 && (
                                    <span className="text-xs bg-destructive/15 text-destructive font-semibold px-2 py-0.5 rounded-full">
                                        {supplier.active_anomalies_count}{" "}
                                        anomalie
                                        {supplier.active_anomalies_count > 1
                                            ? "s"
                                            : ""}
                                    </span>
                                )}
                                <StatusBadge
                                    status={supplier.compliance_status}
                                />
                                <ChevronRight
                                    size={14}
                                    className="text-muted-foreground group-hover:text-foreground transition-colors"
                                />
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
