import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, Users, CheckCircle, AlertTriangle, Clock, XCircle, Upload, TrendingUp } from 'lucide-react'
import { statsApi, documentsApi } from '../api/documents'
import { DocStatusBadge, DocTypeBadge } from '../components/StatusBadge'
import { formatDistanceToNow } from 'date-fns'
import { fr } from 'date-fns/locale'

function StatCard({ icon: Icon, label, value, sub, color = 'blue', loading }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-600',
    green:  'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red:    'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <div className="stat-card">
      <div className={`p-2.5 rounded-lg ${colors[color]}`}>
        <Icon size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        {loading
          ? <div className="h-7 w-16 bg-gray-200 rounded-sm animate-pulse mt-1" />
          : <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
        }
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.dashboard,
    refetchInterval: 15_000,
  })

  const { data: recentDocs, isLoading: loadingDocs } = useQuery({
    queryKey: ['documents', { limit: 8 }],
    queryFn: () => documentsApi.list({ limit: 8 }),
  })

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tableau de bord</h1>
          <p className="text-sm text-gray-500 mt-0.5">Vue d'ensemble de la plateforme</p>
        </div>
        <Link to="/upload" className="btn-primary">
          <Upload size={16} />
          Importer des documents
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={FileText}     label="Total documents"  value={stats?.total_documents}    color="blue"   loading={loadingStats} />
        <StatCard icon={CheckCircle}  label="Traités"          value={stats?.documents_processed} color="green"  loading={loadingStats} sub={`${stats ? Math.round(stats.documents_processed / Math.max(stats.total_documents, 1) * 100) : 0}%`} />
        <StatCard icon={Clock}        label="En cours"         value={stats?.documents_pending}   color="yellow" loading={loadingStats} />
        <StatCard icon={XCircle}      label="Erreurs"          value={stats?.documents_error}     color="red"    loading={loadingStats} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Users}         label="Fournisseurs"     value={stats?.total_suppliers}      color="purple" loading={loadingStats} />
        <StatCard icon={AlertTriangle} label="Anomalies"        value={stats?.unresolved_anomalies} color="yellow" loading={loadingStats} sub="non résolues" />
        <StatCard icon={XCircle}       label="Critiques"        value={stats?.critical_anomalies}   color="red"    loading={loadingStats} />
        <StatCard icon={TrendingUp}    label="Expire bientôt"   value={stats?.documents_expiring_soon} color="yellow" loading={loadingStats} />
      </div>

      {/* Documents récents */}
      <div className="card">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Documents récents</h2>
          <Link to="/documents" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            Voir tout →
          </Link>
        </div>
        <div className="divide-y divide-gray-50">
          {loadingDocs ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 flex items-center gap-4 animate-pulse">
                <div className="h-4 w-24 bg-gray-200 rounded" />
                <div className="h-4 w-16 bg-gray-200 rounded" />
                <div className="h-4 flex-1 bg-gray-200 rounded" />
                <div className="h-4 w-20 bg-gray-200 rounded" />
              </div>
            ))
          ) : recentDocs?.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-400 text-sm">
              Aucun document. <Link to="/upload" className="text-primary-600 hover:underline">Importer</Link>
            </div>
          ) : (
            recentDocs?.map((doc) => (
              <Link
                key={doc.document_id}
                to={`/documents/${doc.document_id}`}
                className="flex items-center gap-4 px-6 py-3.5 hover:bg-gray-50 transition-colors"
              >
                <DocTypeBadge type={doc.doc_type} />
                <span className="flex-1 text-sm text-gray-700 truncate min-w-0">
                  {doc.original_filename}
                </span>
                <DocStatusBadge status={doc.status} />
                <span className="text-xs text-gray-400 whitespace-nowrap">
                  {formatDistanceToNow(new Date(doc.upload_timestamp), { addSuffix: true, locale: fr })}
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
