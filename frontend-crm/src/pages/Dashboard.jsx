import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
    FileText,
    Users,
    CheckCircle,
    AlertTriangle,
    Clock,
    XCircle,
    Upload,
    TrendingUp,
} from "lucide-react";
import { statsApi, documentsApi } from "@/api/documents";
import { DocStatusBadge, DocTypeBadge } from "@/components/StatusBadge";
import { usePermissions } from "@/hooks/usePermissions";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
    EmptyContent,
} from "@/components/ui/empty";

function StatCard({ icon: Icon, label, value, sub, color = "blue", loading }) {
    const colors = {
        blue: "bg-blue-50 text-blue-600",
        green: "bg-green-50 text-green-600",
        yellow: "bg-yellow-50 text-yellow-600",
        red: "bg-red-50 text-red-600",
        purple: "bg-purple-50 text-purple-600",
    };
    return (
        <Card className="py-4 gap-0 shadow-none h-full">
            <CardContent className="px-4 flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${colors[color]}`}>
                    <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-500 font-medium">{label}</p>
                    {loading ? (
                        <div className="h-7 w-16 bg-gray-200 rounded-sm animate-pulse mt-1" />
                    ) : (
                        <div className="flex gap-1 items-baseline">
                            <p className="text-2xl font-bold text-gray-900">
                                {value ?? "—"}
                            </p>
                            {sub && (
                                <p className="text-xs text-gray-400 mt-0.5">
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

export default function Dashboard() {
    const { canUpload } = usePermissions();
    const { data: stats, isLoading: loadingStats } = useQuery({
        queryKey: ["stats"],
        queryFn: statsApi.dashboard,
        refetchInterval: 15_000,
    });

    const { data: recentDocs, isLoading: loadingDocs } = useQuery({
        queryKey: ["documents", { limit: 8 }],
        queryFn: () => documentsApi.list({ limit: 8 }),
    });

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="font-prata text-2xl font-bold text-gray-900">
                        Tableau de bord
                    </h1>
                    <p className="text-sm text-gray-500 mt-0.5">
                        Vue d'ensemble de la plateforme
                    </p>
                </div>
                {canUpload || recentDocs?.length > 0 ? null : (
                    <Button asChild>
                        <Link
                            to="/upload"
                            aria-label="Importer des documents"
                            className="flex items-center gap-0 sm:gap-2"
                        >
                            <Upload size={16} />
                            <span className="hidden sm:inline">
                                Importer des documents
                            </span>
                        </Link>
                    </Button>
                )}
            </div>
            <div className="flex flex-col gap-8">
                <div className="flex flex-wrap gap-4">
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={FileText}
                            label="Total documents"
                            value={stats?.total_documents}
                            color="blue"
                            loading={loadingStats}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={CheckCircle}
                            label="Traités"
                            value={stats?.documents_processed}
                            color="green"
                            loading={loadingStats}
                            sub={`${stats ? Math.round((stats.documents_processed / Math.max(stats.total_documents, 1)) * 100) : 0}%`}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={Clock}
                            label="En cours"
                            value={stats?.documents_pending}
                            color="yellow"
                            loading={loadingStats}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={XCircle}
                            label="Erreurs"
                            value={stats?.documents_error}
                            color="red"
                            loading={loadingStats}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={Users}
                            label="Fournisseurs"
                            value={stats?.total_suppliers}
                            color="purple"
                            loading={loadingStats}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={AlertTriangle}
                            label="Anomalies"
                            value={stats?.unresolved_anomalies}
                            color="yellow"
                            loading={loadingStats}
                            sub="non résolues"
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={XCircle}
                            label="Critiques"
                            value={stats?.critical_anomalies}
                            color="red"
                            loading={loadingStats}
                        />
                    </div>
                    <div className="basis-full sm:basis-[calc(50%-0.5rem)] lg:basis-[calc(25%-0.75rem)] min-w-0">
                        <StatCard
                            icon={TrendingUp}
                            label="Expire bientôt"
                            value={stats?.documents_expiring_soon}
                            color="yellow"
                            loading={loadingStats}
                        />
                    </div>
                </div>
                <Separator />
                <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                        <h2 className="font-prata text-lg font-bold">
                            Documents récents
                        </h2>
                        <Button variant="outline" size="sm" asChild>
                            <Link to="/documents">Voir tout</Link>
                        </Button>
                    </div>
                    {recentDocs?.length === 0 ? (
                        <Card className="shadow-none p-0">
                            <Empty>
                                <EmptyHeader>
                                    <EmptyMedia variant="icon">
                                        <FileText />
                                    </EmptyMedia>
                                    <EmptyTitle>
                                        Aucun document trouvé
                                    </EmptyTitle>
                                    <EmptyDescription>
                                        Commencez par importer des documents pour les voir ici.
                                    </EmptyDescription>
                                </EmptyHeader>
                                <EmptyContent className="flex-row justify-center gap-2">
                                    <Button size="sm" asChild>
                                        <Link to="/upload">
                                            <Upload size={16} />
                                            Importer
                                        </Link>
                                    </Button>
                                </EmptyContent>
                            </Empty>
                        </Card>
                    ) : (
                        <Card className="shadow-none gap-0 p-0">
                            <CardContent className="p-0">
                                <Table className="px-6">
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Type</TableHead>
                                            <TableHead>Nom</TableHead>
                                            <TableHead>Statut</TableHead>
                                            <TableHead className="text-right">
                                                Importé
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {loadingDocs ? (
                                            Array.from({ length: 5 }).map(
                                                (_, i) => (
                                                    <TableRow
                                                        key={i}
                                                        className="animate-pulse"
                                                    >
                                                        <TableCell>
                                                            <div className="h-6 w-20 bg-gray-200 rounded" />
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="h-4 w-56 bg-gray-200 rounded" />
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="h-6 w-24 bg-gray-200 rounded" />
                                                        </TableCell>
                                                        <TableCell className="text-right">
                                                            <div className="h-4 w-20 bg-gray-200 rounded ml-auto" />
                                                        </TableCell>
                                                    </TableRow>
                                                ),
                                            )
                                        ) : (
                                            recentDocs?.map((doc) => (
                                                <TableRow key={doc.document_id}>
                                                    <TableCell>
                                                        <DocTypeBadge
                                                            type={doc.doc_type}
                                                        />
                                                    </TableCell>
                                                    <TableCell className="max-w-[320px]">
                                                        <Link
                                                            to={`/documents/${doc.document_id}`}
                                                            className="text-sm text-gray-700 hover:underline truncate block"
                                                            title={
                                                                doc.original_filename
                                                            }
                                                        >
                                                            {doc.original_filename}
                                                        </Link>
                                                    </TableCell>
                                                    <TableCell>
                                                        <DocStatusBadge
                                                            status={doc.status}
                                                        />
                                                    </TableCell>
                                                    <TableCell className="text-right text-xs text-gray-400">
                                                        {formatDistanceToNow(
                                                            new Date(
                                                                doc.upload_timestamp,
                                                            ),
                                                            {
                                                                addSuffix: true,
                                                                locale: fr,
                                                            },
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            ))
                                        )}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
