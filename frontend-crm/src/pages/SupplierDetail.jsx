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
    RefreshCw,
    OctagonAlert,
    Database,
    Folder,
    Plus,
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
    EmptyContent,
} from "@/components/ui/empty";

function Field({
    label,
    value,
    editValue,
    onChange,
    editing,
    placeholder = "—",
    multiline = false,
    readOnly = false,
}) {
    return (
        <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                {label}
            </p>
            {editing ? (
                multiline ? (
                    <Textarea
                        value={editValue ?? ""}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder={placeholder}
                        rows={4}
                        readOnly={readOnly}
                    />
                ) : (
                    <Input
                        value={editValue ?? ""}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder={placeholder}
                        readOnly={readOnly}
                    />
                )
            ) : (
                <p className="text-sm">
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
                <Spinner size={20} /> Chargement…
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
        <div className="p-8 max-w-6xl mx-auto">
            <Button variant="secondary" size="sm" className="mb-6" asChild>
                <Link to="/suppliers">
                    <ArrowLeft size={15} /> Fournisseurs
                </Link>
            </Button>
            <div className="flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center">
                        <Building2 size={28} className="text-primary-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold">{supplier.name}</h1>
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
                                        <Spinner size={15} />
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
                                    <Spinner size={15} />
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
                    <Card className="gap-0 py-0 shadow-none">
                        <CardHeader className="px-6 py-4 gap-0">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <Building2
                                    size={16}
                                    className="text-primary-600"
                                />
                                Informations fournisseur
                                {editing && (
                                    <span className="text-xs font-normal text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full ml-auto">
                                        Mode édition
                                    </span>
                                )}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="px-6 py-4 border-t">
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
                                    readOnly
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
                                        multiline
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="gap-0 py-0 shadow-none">
                        <CardHeader className="px-6 py-4 gap-0">
                            <div className="flex items-center justify-between gap-3">
                                <CardTitle className="text-base font-semibold flex items-center gap-2">
                                    <Folder size={16} />
                                    Documents
                                </CardTitle>
                                {canUpload && (
                                    <Button variant="outline" size="sm" asChild>
                                        <Link to={`/upload?supplier=${id}`}>
                                            <Plus />
                                            Ajouter
                                        </Link>
                                    </Button>
                                )}
                            </div>
                        </CardHeader>
                        {docs.length === 0 ? (
                            <CardContent className="px-6 py-4 border-t">
                                <Empty>
                                    <EmptyHeader>
                                        <EmptyMedia variant="icon">
                                            <FileText />
                                        </EmptyMedia>
                                        <EmptyTitle>
                                            Aucun document trouvé
                                        </EmptyTitle>
                                        <EmptyDescription>
                                            Commencez par importer des documents
                                            pour les voir ici.
                                        </EmptyDescription>
                                    </EmptyHeader>
                                    {canUpload && (
                                        <EmptyContent className="flex-row justify-center gap-2">
                                            <Button size="sm" asChild>
                                                <Link to={`/upload?supplier=${id}`}>
                                                    <Upload size={16} />
                                                    Importer
                                                </Link>
                                            </Button>
                                        </EmptyContent>
                                    )}
                                </Empty>
                            </CardContent>
                        ) : (
                            <CardContent className="px-6 py-4 border-t">
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
                                            <DocStatusBadge
                                                status={doc.status}
                                            />
                                            <span className="text-xs text-gray-400 whitespace-nowrap hidden lg:block">
                                                {format(
                                                    new Date(
                                                        doc.upload_timestamp,
                                                    ),
                                                    "dd/MM/yyyy",
                                                )}
                                            </span>
                                            {doc.status === "error" &&
                                                canReprocess && (
                                                    <Button
                                                        variant="secondary"
                                                        size="icon"
                                                        onClick={() =>
                                                            reprocessMutation.mutate(
                                                                doc.document_id,
                                                            )
                                                        }
                                                        title="Relancer le traitement"
                                                    >
                                                        <RefreshCw size={14} />
                                                    </Button>
                                                )}
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        )}
                    </Card>
                </div>
                <div className="space-y-4">
                    <Card className="gap-0 py-0 shadow-none">
                        <CardHeader className="px-6 py-4 gap-0">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <OctagonAlert size={16} />
                                Statut conformité
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="px-6 py-4 border-t">
                            <ComplianceBadge
                                status={supplier.compliance_status}
                                size="md"
                            />
                            <div className="mt-4 space-y-2">
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500">
                                        Docs traités
                                    </span>
                                    <span className="font-medium">
                                        {processedDocs.length}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500">
                                        En traitement
                                    </span>
                                    <span className="font-medium">
                                        {pendingDocs.length}
                                    </span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    {processedDocs.length > 0 && (
                        <Card className="gap-0 py-0 shadow-none">
                            <CardHeader className="px-6 py-4 gap-0">
                                <CardTitle className="text-base font-semibold flex items-center gap-2">
                                    <Wand2
                                        size={16}
                                        className="text-primary-600"
                                    />
                                    Données extraites
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="px-6 py-4 border-t">
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
                                        <Button
                                            variant="outline"
                                            onClick={handleAutoFill}
                                        >
                                            <Wand2 size={12} /> Remplir depuis
                                            les documents
                                        </Button>
                                    )}
                            </CardContent>
                        </Card>
                    )}
                    <Card className="gap-0 py-0 shadow-none">
                        <CardHeader className="px-6 py-4 gap-0">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <Database
                                    size={16}
                                    className="text-primary-600"
                                />
                                Métadonnées
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="px-6 py-4 border-t">
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
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
