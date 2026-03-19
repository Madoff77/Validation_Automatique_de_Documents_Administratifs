import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    ArrowLeft,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Clock,
    FileText,
    Calendar,
    ShieldAlert,
    Eye,
} from "lucide-react";
import { suppliersApi, anomaliesApi } from "../api/index";
import DocumentViewer from "../components/DocumentViewer";
import { formatDistanceToNow, format } from "date-fns";
import { fr } from "date-fns/locale";
import toast from "react-hot-toast";
import clsx from "clsx";
import { Input } from "@/components/ui/input";
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

function ComplianceScore({ rate }) {
    const color =
        rate >= 80
                        ? "text-primary"
            : rate >= 50
                            ? "text-chart-2"
                            : "text-destructive";
    const trackColor =
        rate >= 80
                        ? "bg-primary"
            : rate >= 50
                            ? "bg-chart-2"
                            : "bg-destructive";
    return (
        <div className="flex items-center gap-3">
                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div
                    className={clsx(
                        "h-full rounded-full transition-all",
                        trackColor,
                    )}
                    style={{ width: `${rate}%` }}
                />
            </div>
            <span className={clsx("text-sm font-bold w-10 text-right", color)}>
                {rate}%
            </span>
        </div>
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
            className={`inline-flex text-xs font-semibold px-2 py-0.5 rounded-full ${cfg}`}
        >
            {severity}
        </span>
    );
}

export default function SupplierCompliance() {
    const { id } = useParams();
    const qc = useQueryClient();
    const [viewerDocId, setViewerDocId] = useState(null);

    const { data: supplier, isLoading: loadingSupplier } = useQuery({
        queryKey: ["supplier", id],
        queryFn: () => suppliersApi.get(id),
    });

    const { data: compliance } = useQuery({
        queryKey: ["supplier-compliance", id],
        queryFn: () => suppliersApi.compliance(id),
        enabled: !!id,
    });

    const { data: anomalies = [], isLoading: loadingAnomalies } = useQuery({
        queryKey: ["anomalies", { supplier_id: id }],
        queryFn: () => anomaliesApi.list({ supplier_id: id, limit: 50 }),
        enabled: !!id,
        refetchInterval: 20_000,
    });

    const resolveMutation = useMutation({
        mutationFn: ({ aId, notes }) => anomaliesApi.resolve(aId, notes),
        onSuccess: () => {
            qc.invalidateQueries({
                queryKey: ["anomalies", { supplier_id: id }],
            });
            qc.invalidateQueries({ queryKey: ["supplier", id] });
            qc.invalidateQueries({ queryKey: ["stats"] });
            toast.success("Anomalie résolue");
        },
    });

    if (loadingSupplier)
        return (
            <div className="p-8 max-w-4xl mx-auto animate-pulse space-y-4">
                <div className="h-6 bg-muted rounded w-48" />
                <div className="h-32 bg-muted rounded-xl" />
            </div>
        );

    if (!supplier)
        return (
            <div className="p-8 text-center text-muted-foreground">
                Fournisseur introuvable
            </div>
        );

    const cfg =
        STATUS_CONFIG[supplier.compliance_status] || STATUS_CONFIG.pending;
    const { icon: StatusIcon } = cfg;

    const unresolvedAnomalies = anomalies.filter((a) => !a.resolved);
    const resolvedAnomalies = anomalies.filter((a) => a.resolved);

    const complianceRate = compliance
        ? Math.round(
              ((compliance.total_documents - compliance.expired_documents) /
                  Math.max(compliance.total_documents, 1)) *
                  100,
          )
        : 0;

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
                <Link
                    to="/suppliers"
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                >
                    <ArrowLeft size={16} className="text-muted-foreground" />
                </Link>
                <div className="flex-1">
                    <h1 className="text-xl font-bold text-foreground">
                        {supplier.name}
                    </h1>
                    {supplier.siret && (
                        <p className="text-sm text-muted-foreground font-mono">
                            SIRET: {supplier.siret}
                        </p>
                    )}
                </div>
                <span
                    className={clsx(
                        "inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full border",
                        cfg.bg,
                        cfg.color,
                        cfg.border,
                    )}
                >
                    <StatusIcon size={14} /> {cfg.label}
                </span>
            </div>

            <div className="grid grid-cols-3 gap-6 mb-6">
                <div className="col-span-1 card p-5 space-y-3">
                    <h2 className="text-sm font-semibold text-foreground mb-3">
                        Informations
                    </h2>
                    {supplier.contact_email && (
                        <div>
                            <p className="text-xs text-muted-foreground">Email</p>
                            <p className="text-sm text-foreground">
                                {supplier.contact_email}
                            </p>
                        </div>
                    )}
                    {supplier.contact_phone && (
                        <div>
                            <p className="text-xs text-muted-foreground">Téléphone</p>
                            <p className="text-sm text-foreground">
                                {supplier.contact_phone}
                            </p>
                        </div>
                    )}
                    {supplier.address && (
                        <div>
                            <p className="text-xs text-muted-foreground">Adresse</p>
                            <p className="text-sm text-foreground">
                                {supplier.address}
                            </p>
                        </div>
                    )}
                    <div>
                        <p className="text-xs text-muted-foreground">Membre depuis</p>
                        <p className="text-sm text-foreground">
                            {format(
                                new Date(supplier.created_at),
                                "dd MMM yyyy",
                                { locale: fr },
                            )}
                        </p>
                    </div>
                </div>
                <div className="col-span-2 card p-5">
                    <h2 className="text-sm font-semibold text-foreground mb-4">
                        Métriques de conformité
                    </h2>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        {[
                            {
                                label: "Documents totaux",
                                value: compliance?.total_documents ?? "—",
                                icon: FileText,
                                color: "text-primary",
                            },
                            {
                                label: "Expirations actives",
                                value: compliance?.expired_documents ?? "—",
                                icon: Calendar,
                                color: "text-destructive",
                            },
                            {
                                label: "Expire bientôt (30j)",
                                value: compliance?.expiring_soon ?? "—",
                                icon: Clock,
                                color: "text-chart-2",
                            },
                            {
                                label: "Anomalies non résolues",
                                value: unresolvedAnomalies.length,
                                icon: ShieldAlert,
                                color: "text-chart-3",
                            },
                        ].map(({ label, value, icon: Icon, color }) => (
                            <div
                                key={label}
                                className="bg-muted/50 rounded-lg p-3 flex items-center gap-3"
                            >
                                <Icon size={16} className={color} />
                                <div>
                                    <p className="text-xs text-muted-foreground">
                                        {label}
                                    </p>
                                    <p className="text-lg font-bold text-foreground">
                                        {value}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                    {compliance?.total_documents > 0 && (
                        <div>
                            <div className="flex items-center justify-between mb-1.5">
                                <span className="text-xs text-muted-foreground">
                                    Taux de conformité documentaire
                                </span>
                            </div>
                            <ComplianceScore rate={complianceRate} />
                        </div>
                    )}
                </div>
            </div>
            <div className="card">
                <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                    <h2 className="font-semibold text-foreground flex items-center gap-2">
                        <ShieldAlert size={16} className="text-chart-3" />
                        Anomalies
                        {unresolvedAnomalies.length > 0 && (
                            <span className="bg-destructive text-destructive-foreground text-xs font-bold px-1.5 py-0.5 rounded-full">
                                {unresolvedAnomalies.length}
                            </span>
                        )}
                    </h2>
                    <span className="text-xs text-muted-foreground">
                        {anomalies.length} au total
                    </span>
                </div>

                {loadingAnomalies ? (
                    <div className="px-6 py-8 space-y-3">
                        {[...Array(3)].map((_, i) => (
                            <div
                                key={i}
                                className="h-12 bg-muted rounded-lg animate-pulse"
                            />
                        ))}
                    </div>
                ) : anomalies.length === 0 ? (
                    <div className="px-6 py-12 text-center">
                        <CheckCircle
                            size={36}
                            className="mx-auto text-primary mb-3"
                        />
                        <p className="text-sm text-muted-foreground">
                            Aucune anomalie pour ce fournisseur
                        </p>
                    </div>
                ) : (
                    <div>
                        {unresolvedAnomalies.length > 0 && (
                            <div className="divide-y divide-border">
                                {unresolvedAnomalies.map((a) => (
                                    <AnomalyItem
                                        key={a.anomaly_id}
                                        anomaly={a}
                                        onResolve={(notes) =>
                                            resolveMutation.mutate({
                                                aId: a.anomaly_id,
                                                notes,
                                            })
                                        }
                                        onViewDocument={setViewerDocId}
                                    />
                                ))}
                            </div>
                        )}
                        {resolvedAnomalies.length > 0 && (
                            <details className="border-t border-border">
                                <summary className="px-6 py-3 text-xs text-muted-foreground cursor-pointer hover:text-foreground list-none flex items-center gap-2">
                                    <CheckCircle
                                        size={12}
                                        className="text-primary"
                                    />
                                    {resolvedAnomalies.length} anomalie
                                    {resolvedAnomalies.length > 1
                                        ? "s"
                                        : ""}{" "}
                                    résolue
                                    {resolvedAnomalies.length > 1 ? "s" : ""}
                                </summary>
                                <div className="divide-y divide-border">
                                    {resolvedAnomalies.map((a) => (
                                        <AnomalyItem
                                            key={a.anomaly_id}
                                            anomaly={a}
                                            resolved
                                            onViewDocument={setViewerDocId}
                                        />
                                    ))}
                                </div>
                            </details>
                        )}
                    </div>
                )}
            </div>
            {viewerDocId && (
                <DocumentViewer
                    documentId={viewerDocId}
                    onClose={() => setViewerDocId(null)}
                />
            )}
        </div>
    );
}

function AnomalyItem({ anomaly, onResolve, resolved, onViewDocument }) {
    const [expanded, setExpanded] = useState(false);
    const [notes, setNotes] = useState("");

    const docId = anomaly.details?.document_id || anomaly.document_id;

    return (
        <div className={clsx("px-6 py-4", resolved && "opacity-60")}>
            <div className="flex items-start gap-3">
                <SeverityBadge severity={anomaly.severity} />
                <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground">{anomaly.message}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                        <span className="bg-muted px-1.5 py-0.5 rounded">
                            {anomaly.type.replace(/_/g, " ")}
                        </span>
                        <span>
                            {formatDistanceToNow(
                                new Date(anomaly.detected_at),
                                { addSuffix: true, locale: fr },
                            )}
                        </span>
                        {resolved && anomaly.resolved_at && (
                            <span className="text-primary">
                                Résolue{" "}
                                {formatDistanceToNow(
                                    new Date(anomaly.resolved_at),
                                    { addSuffix: true, locale: fr },
                                )}
                            </span>
                        )}
                    </div>
                    {anomaly.details &&
                        Object.keys(anomaly.details).length > 0 && (
                            <div className="mt-1.5 text-xs font-mono text-muted-foreground bg-muted rounded px-2 py-1">
                                {Object.entries(anomaly.details).map(
                                    ([k, v]) => (
                                        <span key={k} className="mr-3">
                                            <span className="text-primary">
                                                {k}:
                                            </span>{" "}
                                            {String(v)}
                                        </span>
                                    ),
                                )}
                            </div>
                        )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    {docId && (
                        <button
                            onClick={() => onViewDocument(docId)}
                            className="text-xs text-muted-foreground hover:text-foreground font-medium px-2 py-1 flex items-center gap-1 rounded bg-muted hover:bg-accent"
                        >
                            <Eye size={14} /> Doc
                        </button>
                    )}
                    {!resolved && onResolve && (
                        <button
                            onClick={() => setExpanded(!expanded)}
                            className="text-xs text-primary hover:text-primary font-medium px-2 py-1 rounded border border-primary/30 hover:bg-primary/10 shrink-0"
                        >
                            {expanded ? "Annuler" : "Résoudre"}
                        </button>
                    )}
                </div>
            </div>
            {expanded && (
                <Field className="mt-4">
                    <Input
                        id={`resolve-notes-${anomaly.anomaly_id}`}
                        placeholder="Notes (optionnel)…"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                    />
                    <Button
                        onClick={() => {
                            onResolve(notes);
                            setExpanded(false);
                        }}
                    >
                        Confirmer
                    </Button>
                </Field>
            )}
        </div>
    );
}
