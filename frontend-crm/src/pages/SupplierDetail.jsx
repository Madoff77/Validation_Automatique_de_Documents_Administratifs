import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    ArrowLeft,
    Building2,
    Edit3,
    Save,
    X,
    Wand2,
    Upload,
    FileText,
    Loader2,
    RefreshCw,
} from "lucide-react";
import { suppliersApi } from "@/api/suppliers";
import { documentsApi } from "@/api/documents";
import {
    ComplianceBadge,
    DocTypeBadge,
    DocStatusBadge,
} from "@/components/StatusBadge";
import { usePermissions } from "@/hooks/usePermissions";
import { format } from "date-fns";

import { toast } from "sonner";
import { Button } from "@/components/ui/button";

// ── Champ de formulaire éditable ─────────────────────────────
function Field({
    label,
    value,
    editValue,
    onChange,
    editing,
    placeholder = "—",
}) {
    return (
        <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                {label}
            </p>
            {editing ? (
                <input
                    className="input text-sm"
                    value={editValue ?? ""}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                />
            ) : (
                <p className="text-sm text-gray-900">
                    {value || (
                        <span className="text-gray-400 italic">
                            Non renseigné
                        </span>
                    )}
                </p>
            )}
        </div>
    );
}

// ── Données extraites d'un document ─────────────────────────
function ExtractedChip({ label, value }) {
    if (!value) return null;
    return (
        <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-blue-500 font-medium">{label}</span>
            <span className="text-xs text-blue-800 font-semibold truncate max-w-40">
                {value}
            </span>
        </div>
    );
}

export default function SupplierDetail() {
    const { id } = useParams();
    const qc = useQueryClient();
    const [editing, setEditing] = useState(false);
    const [editForm, setEditForm] = useState({});
    const [autoFilling, setAutoFilling] = useState(false);
    const { canUpload, canEditSupplier, canReprocess } = usePermissions();

    const { data: supplier, isLoading } = useQuery({
        queryKey: ["supplier", id],
        queryFn: () => suppliersApi.get(id),
    });

    const { data: docs = [] } = useQuery({
        queryKey: ["documents", { supplier_id: id }],
        queryFn: () => documentsApi.list({ supplier_id: id, limit: 50 }),
        enabled: !!id,
    });

    const updateMutation = useMutation({
        mutationFn: (data) => suppliersApi.update(id, data),
        onSuccess: () => {
            qc.invalidateQueries(["supplier", id]);
            setEditing(false);
            toast.success("Fournisseur mis à jour");
        },
        onError: (e) =>
            toast.error(e.response?.data?.detail || "Erreur de mise à jour"),
    });

    const reprocessMutation = useMutation({
        mutationFn: documentsApi.reprocess,
        onSuccess: () => {
            qc.invalidateQueries(["documents", { supplier_id: id }]);
            toast.success("Retraitement lancé");
        },
    });

    // ── Auto-remplissage depuis les données extraites ────────
    const handleAutoFill = () => {
        const processed = docs.filter(
            (d) => d.status === "processed" && d.doc_type,
        );
        if (!processed.length) {
            toast.error(
                "Aucun document traité disponible pour l'auto-remplissage",
            );
            return;
        }

        // Récupérer les données complètes du premier doc traité de chaque type
        const promises = processed
            .slice(0, 5)
            .map((d) => documentsApi.get(d.document_id));
        setAutoFilling(true);

        Promise.allSettled(promises).then((results) => {
            const merged = {};
            results.forEach((r) => {
                if (r.status === "fulfilled" && r.value.extracted) {
                    const ext = r.value.extracted;
                    if (ext.siret && !merged.siret) merged.siret = ext.siret;
                    if (ext.siren && !merged.siren) merged.siren = ext.siren;
                    if (ext.tva_number && !merged.tva_number)
                        merged.tva_number = ext.tva_number;
                    if (ext.raison_sociale && !merged.name)
                        merged.name = ext.raison_sociale;
                    if (ext.adresse && !merged.address)
                        merged.address = ext.adresse;
                }
            });

            if (Object.keys(merged).length === 0) {
                toast.error("Aucune donnée extractible depuis les documents");
                setAutoFilling(false);
                return;
            }

            setEditForm({ ...supplier, ...merged });
            setEditing(true);
            setAutoFilling(false);
            toast.success(
                `${Object.keys(merged).length} champ(s) auto-rempli(s) depuis les documents`,
            );
        });
    };

    if (isLoading)
        return (
            <div className="p-8 flex items-center gap-3 text-gray-500">
                <Loader2 size={20} className="animate-spin" /> Chargement…
            </div>
        );

    if (!supplier)
        return (
            <div className="p-8 text-gray-500">Fournisseur introuvable.</div>
        );

    const startEdit = () => {
        setEditForm({ ...supplier });
        setEditing(true);
    };
    const cancelEdit = () => {
        setEditForm({});
        setEditing(false);
    };
    const saveEdit = () => updateMutation.mutate(editForm);
    const setField = (k) => (v) => setEditForm({ ...editForm, [k]: v });

    const processedDocs = docs.filter((d) => d.status === "processed");
    const pendingDocs = docs.filter(
        (d) => !["processed", "error"].includes(d.status),
    );

    return (
        <div className="p-8 max-w-5xl mx-auto">
            <Link
                to="/suppliers"
                className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6 transition-colors"
            >
                <ArrowLeft size={15} /> Fournisseurs
            </Link>
            <div className="flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center">
                        <Building2 size={28} className="text-primary-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">
                            {supplier.name}
                        </h1>
                        <div className="flex items-center gap-2 mt-1">
                            <ComplianceBadge
                                status={supplier.compliance_status}
                            />
                            <span className="text-sm text-gray-500">
                                {docs.length} document
                                {docs.length > 1 ? "s" : ""}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {!editing ? (
                        <>
                            {canEditSupplier && (
                                <Button
                                    variant="outline"
                                    onClick={handleAutoFill}
                                    disabled={autoFilling}
                                    title="Remplir automatiquement depuis les documents traités"
                                >
                                    {autoFilling ? (
                                        <Loader2
                                            size={15}
                                            className="animate-spin"
                                        />
                                    ) : (
                                        <Wand2 size={15} />
                                    )}
                                    Auto-remplir
                                </Button>
                            )}
                            {canEditSupplier && (
                                <Button variant="outline" onClick={startEdit}>
                                    <Edit3 size={15} /> Modifier
                                </Button>
                            )}
                            {canUpload && (
                                <Button asChild>
                                    <Link to={`/upload?supplier=${id}`}>
                                        <Upload size={15} /> Ajouter document
                                    </Link>
                                </Button>
                            )}
                        </>
                    ) : (
                        <>
                            <Button variant="outline" onClick={cancelEdit}>
                                <X size={15} /> Annuler
                            </Button>
                            <Button
                                onClick={saveEdit}
                                disabled={updateMutation.isPending}
                            >
                                {updateMutation.isPending ? (
                                    <Loader2
                                        size={15}
                                        className="animate-spin"
                                    />
                                ) : (
                                    <Save size={15} />
                                )}
                                Enregistrer
                            </Button>
                        </>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
                <div className="col-span-2 space-y-6">
                    <div className="card p-6">
                        <h2 className="font-semibold text-gray-900 mb-5 flex items-center gap-2">
                            <Building2 size={16} className="text-primary-600" />
                            Informations fournisseur
                            {editing && (
                                <span className="text-xs font-normal text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full ml-auto">
                                    Mode édition
                                </span>
                            )}
                        </h2>
                        <div className="grid grid-cols-2 gap-5">
                            <div className="col-span-2">
                                <Field
                                    label="Raison sociale"
                                    value={supplier.name}
                                    editValue={editForm.name}
                                    onChange={setField("name")}
                                    editing={editing}
                                />
                            </div>
                            <Field
                                label="SIRET"
                                value={supplier.siret}
                                editValue={editForm.siret}
                                onChange={setField("siret")}
                                editing={editing}
                                placeholder="14 chiffres"
                            />
                            <Field
                                label="N° TVA"
                                value={supplier.tva_number}
                                editValue={editForm.tva_number}
                                onChange={setField("tva_number")}
                                editing={editing}
                                placeholder="FR12345678901"
                            />
                            <Field
                                label="Email"
                                value={supplier.email}
                                editValue={editForm.email}
                                onChange={setField("email")}
                                editing={editing}
                            />
                            <Field
                                label="Téléphone"
                                value={supplier.phone}
                                editValue={editForm.phone}
                                onChange={setField("phone")}
                                editing={editing}
                            />
                            <div className="col-span-2">
                                <Field
                                    label="Adresse"
                                    value={supplier.address}
                                    editValue={editForm.address}
                                    onChange={setField("address")}
                                    editing={editing}
                                />
                            </div>
                            <div className="col-span-2">
                                <Field
                                    label="Notes"
                                    value={supplier.notes}
                                    editValue={editForm.notes}
                                    onChange={setField("notes")}
                                    editing={editing}
                                />
                            </div>
                        </div>
                    </div>
                    <div className="card">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                            <h2 className="font-semibold text-gray-900">
                                Documents
                            </h2>
                            {canUpload && (
                                <Link
                                    to={`/upload?supplier=${id}`}
                                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                                >
                                    + Ajouter
                                </Link>
                            )}
                        </div>
                        {docs.length === 0 ? (
                            <div className="px-6 py-12 text-center">
                                <FileText
                                    size={36}
                                    className="mx-auto text-gray-300 mb-3"
                                />
                                <p className="text-sm text-gray-400">
                                    Aucun document importé
                                </p>
                                {canUpload && (
                                    <Button asChild>
                                        <Link to={`/upload?supplier=${id}`}>
                                            <Upload size={14} /> Importer
                                        </Link>
                                    </Button>
                                )}
                            </div>
                        ) : (
                            <div className="divide-y divide-gray-50">
                                {docs.map((doc) => (
                                    <div
                                        key={doc.document_id}
                                        className="flex items-center gap-3 px-6 py-3.5"
                                    >
                                        <DocTypeBadge type={doc.doc_type} />
                                        <Link
                                            to={`/documents/${doc.document_id}`}
                                            className="flex-1 text-sm text-gray-700 hover:text-primary-600 truncate min-w-0"
                                        >
                                            {doc.original_filename}
                                        </Link>
                                        <DocStatusBadge status={doc.status} />
                                        <span className="text-xs text-gray-400 whitespace-nowrap hidden lg:block">
                                            {format(
                                                new Date(doc.upload_timestamp),
                                                "dd/MM/yyyy",
                                            )}
                                        </span>
                                        {doc.status === "error" &&
                                            canReprocess && (
                                                <button
                                                    onClick={() =>
                                                        reprocessMutation.mutate(
                                                            doc.document_id,
                                                        )
                                                    }
                                                    className="text-gray-400 hover:text-primary-600 transition-colors"
                                                    title="Relancer le traitement"
                                                >
                                                    <RefreshCw size={14} />
                                                </button>
                                            )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
                <div className="space-y-4">
                    <div className="card p-5">
                        <h3 className="text-sm font-semibold text-gray-900 mb-4">
                            Statut conformité
                        </h3>
                        <ComplianceBadge
                            status={supplier.compliance_status}
                            size="md"
                        />
                        <div className="mt-4 space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-gray-500">
                                    Docs traités
                                </span>
                                <span className="font-medium text-gray-900">
                                    {processedDocs.length}
                                </span>
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-gray-500">
                                    En traitement
                                </span>
                                <span className="font-medium text-gray-900">
                                    {pendingDocs.length}
                                </span>
                            </div>
                        </div>
                    </div>
                    {processedDocs.length > 0 && (
                        <div className="card p-5">
                            <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                <Wand2 size={14} className="text-primary-600" />
                                Données extraites
                            </h3>
                            <p className="text-xs text-gray-400 mb-3">
                                Depuis {processedDocs.length} document
                                {processedDocs.length > 1 ? "s" : ""} traité
                                {processedDocs.length > 1 ? "s" : ""}
                            </p>
                            <div className="space-y-2">
                                {supplier.siret && (
                                    <ExtractedChip
                                        label="SIRET"
                                        value={supplier.siret}
                                    />
                                )}
                                {supplier.tva_number && (
                                    <ExtractedChip
                                        label="TVA"
                                        value={supplier.tva_number}
                                    />
                                )}
                                {supplier.email && (
                                    <ExtractedChip
                                        label="Email"
                                        value={supplier.email}
                                    />
                                )}
                            </div>
                            {!supplier.siret &&
                                !supplier.tva_number &&
                                canEditSupplier && (
                                    <Button variant="outline"
                                        onClick={handleAutoFill}
                                    >
                                        <Wand2 size={12} /> Remplir depuis les
                                        documents
                                    </Button>
                                )}
                        </div>
                    )}
                    <div className="card p-5">
                        <h3 className="text-sm font-semibold text-gray-900 mb-3">
                            Métadonnées
                        </h3>
                        <div className="space-y-2 text-xs text-gray-500">
                            <div>
                                <span className="block text-gray-400">
                                    Créé le
                                </span>
                                <span>
                                    {format(
                                        new Date(supplier.created_at),
                                        "dd/MM/yyyy HH:mm",
                                    )}
                                </span>
                            </div>
                            <div>
                                <span className="block text-gray-400">
                                    Modifié le
                                </span>
                                <span>
                                    {format(
                                        new Date(supplier.updated_at),
                                        "dd/MM/yyyy HH:mm",
                                    )}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
