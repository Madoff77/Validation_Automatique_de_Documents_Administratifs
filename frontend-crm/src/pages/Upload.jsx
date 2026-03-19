import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
    Upload as UploadIcon,
    File,
    X,
    CheckCircle,
    AlertCircle,
    Loader2,
    ArrowLeft,
} from "lucide-react";
import { suppliersApi } from "@/api/suppliers";
import { documentsApi } from "@/api/documents";
import clsx from "clsx";

import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const ACCEPT = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/tiff": [".tiff", ".tif"],
};

const STATUS_ICON = {
    idle: <File size={16} className="text-gray-400" />,
    uploading: <Loader2 size={16} className="animate-spin text-blue-500" />,
    success: <CheckCircle size={16} className="text-green-500" />,
    error: <AlertCircle size={16} className="text-red-500" />,
};

export default function Upload() {
    const [searchParams] = useSearchParams();
    const preselected = searchParams.get("supplier");

    const [supplierId, setSupplierId] = useState(preselected || "");
    const [files, setFiles] = useState([]); // [{file, status, progress, error, docId}]

    const { data: suppliers = [], isLoading: suppliersLoading } = useQuery({
        queryKey: ["suppliers"],
        queryFn: () => suppliersApi.list(),
    });

    const onDrop = useCallback((accepted) => {
        const newFiles = accepted.map((file) => ({
            id: Math.random().toString(36).slice(2),
            file,
            status: "idle",
            progress: 0,
            error: null,
            docId: null,
        }));
        setFiles((prev) => [...prev, ...newFiles]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: ACCEPT,
        maxSize: 50 * 1024 * 1024,
        onDropRejected: (rej) => {
            rej.forEach((r) =>
                toast.error(`${r.file.name} : ${r.errors[0]?.message}`),
            );
        },
    });

    const removeFile = (id) =>
        setFiles((prev) => prev.filter((f) => f.id !== id));

    const uploadFile = async (item) => {
        setFiles((prev) =>
            prev.map((f) =>
                f.id === item.id ? { ...f, status: "uploading" } : f,
            ),
        );
        try {
            const data = await documentsApi.upload(
                supplierId,
                item.file,
                (pct) => {
                    setFiles((prev) =>
                        prev.map((f) =>
                            f.id === item.id ? { ...f, progress: pct } : f,
                        ),
                    );
                },
            );
            setFiles((prev) =>
                prev.map((f) =>
                    f.id === item.id
                        ? {
                              ...f,
                              status: "success",
                              progress: 100,
                              docId: data.document_id,
                          }
                        : f,
                ),
            );
        } catch (e) {
            const msg = e.response?.data?.detail || "Erreur d'upload";
            setFiles((prev) =>
                prev.map((f) =>
                    f.id === item.id
                        ? { ...f, status: "error", error: msg }
                        : f,
                ),
            );
        }
    };

    const uploadAll = async () => {
        if (!supplierId) {
            toast.error("Sélectionnez un fournisseur");
            return;
        }
        const pending = files.filter((f) => f.status === "idle");
        if (!pending.length) {
            toast.error("Aucun fichier à envoyer");
            return;
        }
        await Promise.all(pending.map(uploadFile));
        toast.success(`${pending.length} fichier(s) envoyé(s)`);
    };

    const pendingCount = files.filter((f) => f.status === "idle").length;
    const successCount = files.filter((f) => f.status === "success").length;

    return (
        <div className="p-8 max-w-3xl mx-auto">
            <Button variant="secondary" size="sm" className="mb-6" asChild>
                <Link
                    to="/upload"
                >
                    <ArrowLeft size={15} /> Retour
                </Link>
            </Button>

            <h1 className="font-prata text-2xl font-bold text-gray-900 mb-1">
                Importer des documents
            </h1>
            <p className="text-sm text-gray-500 mb-8">
                Formats supportés : PDF, JPEG, PNG, TIFF — Max 50 Mo par fichier
            </p>
            <Field className="w-full max-w-64 mb-6">
                <FieldLabel>Fournisseur</FieldLabel>
                <Select
                    value={supplierId || undefined}
                    onValueChange={setSupplierId}
                    disabled={suppliersLoading || suppliers.length === 0}
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Sélectionner un fournisseur" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectGroup>
                            {suppliers.length === 0 ? (
                                <SelectItem value="no-supplier" disabled>
                                    Aucun fournisseur disponible
                                </SelectItem>
                            ) : (
                                suppliers.map((s) => (
                                    <SelectItem
                                        key={s.supplier_id}
                                        value={String(s.supplier_id)}
                                    >
                                        {s.name}
                                    </SelectItem>
                                ))
                            )}
                        </SelectGroup>
                    </SelectContent>
                </Select>
            </Field>
            <div
                {...getRootProps()}
                className={clsx(
                    "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all mb-6",
                    isDragActive
                        ? "border-primary-500 bg-primary-50"
                        : "border-gray-300 hover:border-primary-400 hover:bg-gray-50",
                )}
            >
                <input {...getInputProps()} />
                <UploadIcon
                    size={36}
                    className={clsx(
                        "mx-auto mb-3",
                        isDragActive ? "text-primary-500" : "text-gray-400",
                    )}
                />
                <p className="font-medium text-gray-700">
                    {isDragActive
                        ? "Déposez les fichiers ici…"
                        : "Glissez-déposez vos documents"}
                </p>
                <p className="text-sm text-gray-400 mt-1">
                    ou{" "}
                    <span className="text-primary-600">
                        cliquez pour sélectionner
                    </span>
                </p>
            </div>
            {files.length > 0 && (
                <div className="card mb-6">
                    <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-700">
                            {files.length} fichier{files.length > 1 ? "s" : ""}
                            {successCount > 0 && (
                                <span className="text-green-600 ml-2">
                                    · {successCount} envoyé
                                    {successCount > 1 ? "s" : ""}
                                </span>
                            )}
                        </span>
                        <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => setFiles([])}
                            className="text-xs text-gray-400 hover:text-gray-600"
                        >
                            Tout effacer
                        </Button>
                    </div>
                    <div className="divide-y divide-gray-50">
                        {files.map((item) => (
                            <div
                                key={item.id}
                                className="flex items-center gap-3 px-5 py-3"
                            >
                                {STATUS_ICON[item.status]}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-gray-800 truncate">
                                        {item.file.name}
                                    </p>
                                    <p className="text-xs text-gray-400">
                                        {(item.file.size / 1024).toFixed(0)} Ko
                                        {item.error && (
                                            <span className="text-red-500 ml-2">
                                                {item.error}
                                            </span>
                                        )}
                                        {item.status === "uploading" && (
                                            <span className="text-blue-500 ml-2">
                                                {item.progress}%
                                            </span>
                                        )}
                                        {item.status === "success" &&
                                            item.docId && (
                                                <Link
                                                    to={`/documents/${item.docId}`}
                                                    className="text-green-600 ml-2 hover:underline"
                                                >
                                                    Voir le document →
                                                </Link>
                                            )}
                                    </p>
                                    {item.status === "uploading" && (
                                        <div className="mt-1.5 h-1 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-primary-500 transition-all rounded-full"
                                                style={{
                                                    width: `${item.progress}%`,
                                                }}
                                            />
                                        </div>
                                    )}
                                </div>
                                {item.status === "idle" && (
                                    <button
                                        onClick={() => removeFile(item.id)}
                                        className="text-gray-300 hover:text-gray-500"
                                    >
                                        <X size={16} />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
            <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">
                    {pendingCount > 0
                        ? `${pendingCount} fichier${pendingCount > 1 ? "s" : ""} prêt${pendingCount > 1 ? "s" : ""} à envoyer`
                        : successCount > 0
                          ? "Tous les fichiers ont été envoyés"
                          : "Aucun fichier sélectionné"}
                </p>
                <Button
                    onClick={uploadAll}
                    disabled={!pendingCount || !supplierId}
                >
                    <UploadIcon size={15} />
                    Envoyer {pendingCount > 0 ? `(${pendingCount})` : ""}
                </Button>
            </div>
        </div>
    );
}
