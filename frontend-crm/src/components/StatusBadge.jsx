import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const DOC_STATUS = {
    pending: { label: "En attente", cls: "bg-background text-gray-600" },
    preprocessing: {
        label: "Traitement…",
        cls: "bg-blue-100 text-blue-700 animate-pulse",
    },
    ocr_done: { label: "OCR OK", cls: "bg-indigo-100 text-indigo-700" },
    classified: { label: "Classifié", cls: "bg-purple-100 text-purple-700" },
    extracted: { label: "Extrait", cls: "bg-cyan-100 text-cyan-700" },
    validated: { label: "Validé", cls: "bg-teal-100 text-teal-700" },
    processed: { label: "Traité", cls: "bg-green-100 text-green-700" },
    error: { label: "Erreur", cls: "bg-red-100 text-red-700" },
};

const DOC_TYPE = {
    FACTURE: {
        label: "Facture",
        cls: "bg-blue-50 text-blue-700 border border-blue-200",
    },
    DEVIS: {
        label: "Devis",
        cls: "bg-violet-50 text-violet-700 border border-violet-200",
    },
    SIRET: {
        label: "SIRET",
        cls: "bg-green-50 text-green-700 border border-green-200",
    },
    URSSAF: {
        label: "URSSAF",
        cls: "bg-orange-50 text-orange-700 border border-orange-200",
    },
    KBIS: {
        label: "Kbis",
        cls: "bg-pink-50 text-pink-700 border border-pink-200",
    },
    RIB: {
        label: "RIB",
        cls: "bg-yellow-50 text-yellow-700 border border-yellow-200",
    },
    UNKNOWN: {
        label: "Inconnu",
        cls: "bg-card text-gray-500 border border-border",
    },
};

const COMPLIANCE = {
    compliant: { label: "Conforme", cls: "bg-green-100 text-green-700" },
    warning: { label: "Avertissement", cls: "bg-yellow-100 text-yellow-700" },
    non_compliant: { label: "Non conforme", cls: "bg-red-100 text-red-700" },
    pending: { label: "En attente", cls: "bg-background text-gray-500" },
};

const VALIDATION = {
    ok: { label: "Valide", cls: "bg-green-100 text-green-700" },
    warning: { label: "Alerte", cls: "bg-yellow-100 text-yellow-700" },
    error: { label: "Erreur", cls: "bg-red-100 text-red-700" },
    pending: { label: "En cours", cls: "bg-background text-gray-500" },
};

function StatusBadge({ label, cls, size = "sm" }) {
    return (
        <Badge
            variant="secondary"
            className={cn(
                "font-medium rounded-full",
                size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
                cls,
            )}
        >
            {label}
        </Badge>
    );
}

export function DocStatusBadge({ status, size }) {
    const cfg = DOC_STATUS[status] || DOC_STATUS.pending;
    return <StatusBadge {...cfg} size={size} />;
}

export function DocTypeBadge({ type, size }) {
    const cfg = DOC_TYPE[type] || DOC_TYPE.UNKNOWN;
    return <StatusBadge {...cfg} size={size} />;
}

export function ComplianceBadge({ status, size }) {
    const cfg = COMPLIANCE[status] || COMPLIANCE.pending;
    return <StatusBadge {...cfg} size={size} />;
}

export function ValidationBadge({ status, size }) {
    const cfg = VALIDATION[status] || VALIDATION.pending;
    return <StatusBadge {...cfg} size={size} />;
}
