import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileText, Search, Upload } from "lucide-react";
import { documentsApi } from "../api/documents";
import { DocStatusBadge, DocTypeBadge } from "../components/StatusBadge";
import { usePermissions } from "../hooks/usePermissions";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput
} from "@/components/ui/input-group";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const DOC_TYPES = ["FACTURE", "DEVIS", "SIRET", "URSSAF", "KBIS", "RIB"];
const STATUSES = [
    "pending",
    "preprocessing",
    "ocr_done",
    "classified",
    "extracted",
    "validated",
    "processed",
    "error",
];

export default function Documents() {
    const [filters, setFilters] = useState({ doc_type: "", status: "" });
    const [search, setSearch] = useState("");
    const { canUpload } = usePermissions();

    const { data: docs = [], isLoading } = useQuery({
        queryKey: ["documents", filters],
        queryFn: () =>
            documentsApi.list({
                doc_type: filters.doc_type || undefined,
                status: filters.status || undefined,
                limit: 100,
            }),
        refetchInterval: (data) => {
            if (!Array.isArray(data)) return 5_000;
            const hasInProgress = data.some(
                (d) => !["processed", "error"].includes(d.status)
            );
            return hasInProgress ? 3_000 : false;
        },
    });

    const filtered = search
        ? docs.filter((d) =>
              d.original_filename.toLowerCase().includes(search.toLowerCase()),
          )
        : docs;

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="font-prata text-2xl font-bold text-gray-900">
                        Documents
                    </h1>
                    <p className="text-sm text-gray-500 mt-0.5">
                        {filtered.length} document
                        {filtered.length > 1 ? "s" : ""}
                    </p>
                </div>
                {canUpload && (
                    <Button asChild>
                        <Link to="/upload">
                            <Upload size={16} /> Importer
                        </Link>
                    </Button>
                )}
            </div>
            <div className="flex flex-wrap gap-3 mb-6">
                <Field className="max-w-xs w-full">
                    <InputGroup>
                        <InputGroupAddon>
                            <Search size={16} />
                        </InputGroupAddon>
                        <InputGroupInput
                            id="search"
                            placeholder="Rechercher…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </InputGroup>
                </Field>
                <Select
                    value={filters.doc_type || "all"}
                    onValueChange={(value) =>
                        setFilters({
                            ...filters,
                            doc_type: value === "all" ? "" : value,
                        })
                    }
                >
                    <SelectTrigger className="max-w-40 w-full text-sm">
                        <SelectValue placeholder="Tous les types" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Tous les types</SelectItem>
                        {DOC_TYPES.map((t) => (
                            <SelectItem key={t} value={t}>
                                {t}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Select
                    value={filters.status || "all"}
                    onValueChange={(value) =>
                        setFilters({
                            ...filters,
                            status: value === "all" ? "" : value,
                        })
                    }
                >
                    <SelectTrigger className="max-w-40 w-full text-sm">
                        <SelectValue placeholder="Tous les statuts" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Tous les statuts</SelectItem>
                        {STATUSES.map((s) => (
                            <SelectItem key={s} value={s}>
                                {s}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            <div className="card overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-gray-50 border-b border-gray-100">
                            <th className="text-left px-5 py-3 font-medium text-gray-500">
                                Fichier
                            </th>
                            <th className="text-left px-4 py-3 font-medium text-gray-500">
                                Type
                            </th>
                            <th className="text-left px-4 py-3 font-medium text-gray-500">
                                Statut
                            </th>
                            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden lg:table-cell">
                                Validation
                            </th>
                            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden md:table-cell">
                                Confiance
                            </th>
                            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden md:table-cell">
                                Importé le
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                        {isLoading ? (
                            Array.from({ length: 8 }).map((_, i) => (
                                <tr key={i} className="animate-pulse">
                                    {Array.from({ length: 6 }).map((_, j) => (
                                        <td key={j} className="px-5 py-4">
                                            <div className="h-4 bg-gray-100 rounded-sm w-3/4" />
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : filtered.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={6}
                                    className="px-5 py-16 text-center text-gray-400"
                                >
                                    <FileText
                                        size={36}
                                        className="mx-auto mb-3 text-gray-300"
                                    />
                                    Aucun document trouvé
                                </td>
                            </tr>
                        ) : (
                            filtered.map((doc) => (
                                <tr
                                    key={doc.document_id}
                                    className="hover:bg-gray-50 transition-colors"
                                >
                                    <td className="px-5 py-3.5">
                                        <Link
                                            to={`/documents/${doc.document_id}`}
                                            className="text-gray-800 hover:text-primary-600 font-medium truncate max-w-xs block"
                                        >
                                            {doc.original_filename}
                                        </Link>
                                    </td>
                                    <td className="px-4 py-3.5">
                                        <DocTypeBadge type={doc.doc_type} />
                                    </td>
                                    <td className="px-4 py-3.5">
                                        <DocStatusBadge status={doc.status} />
                                    </td>
                                    <td className="px-4 py-3.5 hidden lg:table-cell">
                                        {doc.validation_status && (
                                            <span
                                                className={`text-xs font-medium ${
                                                    doc.validation_status ===
                                                    "ok"
                                                        ? "text-green-600"
                                                        : doc.validation_status ===
                                                            "warning"
                                                          ? "text-yellow-600"
                                                          : "text-red-600"
                                                }`}
                                            >
                                                {doc.validation_status === "ok"
                                                    ? "✓ OK"
                                                    : doc.validation_status ===
                                                        "warning"
                                                      ? "⚠ Alerte"
                                                      : doc.validation_status ===
                                                          "error"
                                                        ? "✗ Erreur"
                                                        : "—"}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-4 py-3.5 hidden md:table-cell text-gray-500">
                                        {doc.classification_confidence
                                            ? `${(doc.classification_confidence * 100).toFixed(0)}%`
                                            : "—"}
                                    </td>
                                    <td className="px-4 py-3.5 hidden md:table-cell text-gray-400 text-xs">
                                        {format(
                                            new Date(doc.upload_timestamp),
                                            "dd/MM/yyyy HH:mm",
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
