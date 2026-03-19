import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    Building2,
    Calendar,
    CreditCard,
    Euro,
    FileText,
} from "lucide-react";
import { documentsApi } from "../api/documents";
import apiClient from "../api/client";
import { Spinner } from "./ui/spinner";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const formatAmount = (v) =>
    v != null
        ? `${v.toLocaleString("fr-FR", { minimumFractionDigits: 2 })} €`
        : "N/A";

function FieldRow({ icon: Icon, label, value }) {
    if (!value) return null;
    return (
        <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
            <div className="mt-0.5">
                {Icon ? (
                    <Icon size={16} className="text-gray-400" />
                ) : (
                    <div className="w-4" />
                )}
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 font-medium">{label}</p>
                <p className="text-sm text-gray-900 font-semibold">{value}</p>
            </div>
        </div>
    );
}

function SkeletonField() {
    return (
        <div className="flex items-start gap-3 py-3 border-b border-border last:border-0 animate-pulse">
            <div className="w-4 h-4 bg-gray-200 rounded mt-0.5" />
            <div className="flex-1 space-y-2">
                <div className="h-3 bg-gray-200 rounded w-1/3" />
                <div className="h-4 bg-gray-200 rounded w-2/3" />
            </div>
        </div>
    );
}

export default function DocumentViewer({ documentId, open, onOpenChange }) {
    const [iframeLoaded, setIframeLoaded] = useState(false);

    const { data: doc, isLoading } = useQuery({
        queryKey: ["document", documentId],
        queryFn: () => documentsApi.get(documentId),
        enabled: !!documentId && open,
    });

    const viewUrl = `${apiClient.defaults.baseURL}/documents/${documentId}/view`;
    const ext = doc?.extracted || {};

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-full max-w-[90vw] sm:max-w-280 max-h-[90vh] h-full p-0 gap-0 overflow-hidden flex flex-col">
                <DialogHeader className="sticky top-0 z-20 shrink-0 flex-row items-center gap-3 px-6 py-4 border-b border-border bg-card">
                    <div className="p-2 bg-primary/10 rounded-lg">
                        <FileText size={20} className="text-primary" />
                    </div>
                    <div>
                        <DialogTitle className="text-lg">
                            {doc?.original_filename ||
                                "Visualisation du document"}
                        </DialogTitle>
                        <p className="text-xs text-gray-500 font-mono">
                            ID: {documentId}
                        </p>
                    </div>
                </DialogHeader>
                <div className="flex-1 overflow-hidden min-h-0 flex">
                    <div className="flex-1 bg-background relative border-r border-border flex items-center justify-center">
                        {!iframeLoaded && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 bg-background z-10">
                                <Spinner />
                            </div>
                        )}
                        <iframe
                            src={viewUrl}
                            title="Document Viewer"
                            className={`w-full h-full border-0 transition-opacity duration-300 ${iframeLoaded ? "opacity-100" : "opacity-0"}`}
                            onLoad={() => setIframeLoaded(true)}
                        />
                    </div>
                    <div className="w-96 bg-white overflow-y-auto">
                        <div className="p-6">
                            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-6 border-b border-border pb-2">
                                Données Extraites
                            </h3>

                            {isLoading ? (
                                <div className="space-y-1">
                                    <SkeletonField />
                                    <SkeletonField />
                                    <SkeletonField />
                                    <SkeletonField />
                                    <SkeletonField />
                                    <SkeletonField />
                                </div>
                            ) : Object.keys(ext).length > 0 ? (
                                <div className="space-y-1">
                                    <FieldRow
                                        icon={Building2}
                                        label="Raison sociale"
                                        value={ext.raison_sociale}
                                    />
                                    <FieldRow
                                        icon={Building2}
                                        label="SIRET"
                                        value={ext.siret}
                                    />
                                    <FieldRow
                                        icon={Building2}
                                        label="SIREN"
                                        value={ext.siren}
                                    />
                                    <FieldRow
                                        icon={Building2}
                                        label="N° TVA"
                                        value={ext.tva_number}
                                    />
                                    <FieldRow
                                        icon={Euro}
                                        label="Montant HT"
                                        value={
                                            ext.montant_ht
                                                ? formatAmount(ext.montant_ht)
                                                : null
                                        }
                                    />
                                    <FieldRow
                                        icon={Euro}
                                        label="Montant TVA"
                                        value={
                                            ext.montant_tva
                                                ? formatAmount(ext.montant_tva)
                                                : null
                                        }
                                    />
                                    <FieldRow
                                        icon={Euro}
                                        label="Montant TTC"
                                        value={
                                            ext.montant_ttc
                                                ? formatAmount(ext.montant_ttc)
                                                : null
                                        }
                                    />
                                    <FieldRow
                                        icon={Calendar}
                                        label="Date d'émission"
                                        value={ext.date_emission}
                                    />
                                    <FieldRow
                                        icon={Calendar}
                                        label="Date d'échéance"
                                        value={ext.date_echeance}
                                    />
                                    <FieldRow
                                        icon={CreditCard}
                                        label="IBAN"
                                        value={ext.iban}
                                    />
                                </div>
                            ) : (
                                <div className="text-center py-12 text-gray-500">
                                    <FileText
                                        size={32}
                                        className="mx-auto text-gray-300 mb-3"
                                    />
                                    <p className="text-sm">
                                        Aucune donnée extraite ou en cours de
                                        traitement.
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
