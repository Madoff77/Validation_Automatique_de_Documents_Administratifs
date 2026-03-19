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
import { Card } from "@/components/ui/card";
import {
    InputGroup,
    InputGroupAddon,
    InputGroupInput,
} from "@/components/ui/input-group";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty";

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
            <Card className="shadow-none p-0">
                {isLoading ? (
                    <Table className="px-6 text-sm">
                        <TableHeader>
                            <TableRow>
                                <TableHead>Fichier</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Statut</TableHead>
                                <TableHead className="hidden lg:table-cell">
                                    Validation
                                </TableHead>
                                <TableHead className="hidden md:table-cell">
                                    Confiance
                                </TableHead>
                                <TableHead className="hidden md:table-cell">
                                    Importé le
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {Array.from({ length: 8 }).map((_, i) => (
                                <TableRow key={i} className="animate-pulse">
                                    {Array.from({ length: 6 }).map((_, j) => (
                                        <TableCell key={j}>
                                            <div className="h-4 bg-background rounded-sm w-3/4" />
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : filtered.length === 0 ? (
                    <Empty>
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <FileText />
                            </EmptyMedia>
                            <EmptyTitle>Aucun document trouvé</EmptyTitle>
                            <EmptyDescription>
                                Essayez d'ajuster vos filtres ou de relancer une recherche.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : (
                    <Table className="px-6 text-sm">
                        <TableHeader>
                            <TableRow>
                                <TableHead>Fichier</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Statut</TableHead>
                                <TableHead className="hidden lg:table-cell">
                                    Validation
                                </TableHead>
                                <TableHead className="hidden md:table-cell">
                                    Confiance
                                </TableHead>
                                <TableHead className="hidden md:table-cell">
                                    Importé le
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filtered.map((doc) => (
                                <TableRow key={doc.document_id}>
                                    <TableCell className="max-w-xs">
                                        <Link
                                            to={`/documents/${doc.document_id}`}
                                            className="text-gray-800 hover:text-primary-600 font-medium truncate max-w-xs block"
                                        >
                                            {doc.original_filename}
                                        </Link>
                                    </TableCell>
                                    <TableCell>
                                        <DocTypeBadge type={doc.doc_type} />
                                    </TableCell>
                                    <TableCell>
                                        <DocStatusBadge status={doc.status} />
                                    </TableCell>
                                    <TableCell className="hidden lg:table-cell">
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
                                                    ? "OK"
                                                    : doc.validation_status ===
                                                        "warning"
                                                      ? "Alerte"
                                                      : doc.validation_status ===
                                                          "error"
                                                        ? "Erreur"
                                                        : "—"}
                                            </span>
                                        )}
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell text-gray-500">
                                        {doc.classification_confidence
                                            ? `${(doc.classification_confidence * 100).toFixed(0)}%`
                                            : "—"}
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell text-gray-400 text-xs">
                                        {format(
                                            new Date(doc.upload_timestamp),
                                            "dd/MM/yyyy HH:mm",
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </Card>
        </div>
    );
}
