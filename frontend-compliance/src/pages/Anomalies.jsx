import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, Filter, RefreshCw, X, Eye } from 'lucide-react'
import { anomaliesApi } from '../api/index'
import DocumentViewer from '../components/DocumentViewer'
import { usePermissions } from '../hooks/usePermissions'
import { formatDistanceToNow, format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { toast } from 'sonner';
import clsx from 'clsx'

const SEVERITY_OPTIONS = ['', 'error', 'warning', 'info']
const TYPE_OPTIONS = [
  '', 'SIRET_MISMATCH', 'DATE_EXPIRED', 'TVA_INCOHERENCE',
  'MISSING_FIELD', 'FORMAT_ERROR', 'KBIS_EXPIRED', 'URSSAF_EXPIRED',
]

function SeverityBadge({ severity }) {
  const cfg = {
    error:   'bg-red-100 text-red-700 border border-red-200',
    warning: 'bg-yellow-100 text-yellow-700 border border-yellow-200',
    info:    'bg-blue-100 text-blue-600 border border-blue-200',
  }[severity] || 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full ${cfg}`}>
      {severity === 'error' && <span className="w-1.5 h-1.5 rounded-full bg-red-500 mr-1" />}
      {severity === 'warning' && <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 mr-1" />}
      {severity === 'info' && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1" />}
      {severity}
    </span>
  )
}

export default function Anomalies() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState({ severity: '', type: '', resolved: false })
  const [showResolved, setShowResolved] = useState(false)
  const [viewerDocId, setViewerDocId] = useState(null)

  const { data: anomalies = [], isLoading, refetch } = useQuery({
    queryKey: ['anomalies', filters, showResolved],
    queryFn: () => anomaliesApi.list({
      ...(filters.severity && { severity: filters.severity }),
      ...(filters.type && { type: filters.type }),
      resolved: showResolved,
      limit: 100,
    }),
    refetchInterval: 20_000,
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id }) => anomaliesApi.resolve(id, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['anomalies'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      toast.success('Anomalie résolue')
    },
    onError: () => toast.error('Erreur lors de la résolution'),
  })

  const clearFilters = () => setFilters({ severity: '', type: '', resolved: false })
  const hasFilters = filters.severity || filters.type

  const grouped = anomalies.reduce((acc, a) => {
    const key = a.severity
    if (!acc[key]) acc[key] = []
    acc[key].push(a)
    return acc
  }, {})
  const order = ['error', 'warning', 'info']

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Anomalies</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {anomalies.length} anomalie{anomalies.length > 1 ? 's' : ''} {showResolved ? 'résolues' : 'non résolues'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => refetch()} className="btn-secondary flex items-center gap-2">
            <RefreshCw size={14} /> Actualiser
          </button>
          <button
            onClick={() => setShowResolved(!showResolved)}
            className={clsx('btn-secondary flex items-center gap-2', showResolved && 'bg-green-50 text-green-700 border-green-200')}
          >
            <CheckCircle size={14} />
            {showResolved ? 'Non résolues' : 'Voir résolues'}
          </button>
        </div>
      </div>
      <div className="card p-4 mb-6 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Filter size={14} /> Filtres
        </div>
        <select
          className="input py-1.5 text-sm w-36"
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
        >
          <option value="">Toutes sévérités</option>
          {SEVERITY_OPTIONS.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="input py-1.5 text-sm w-52"
          value={filters.type}
          onChange={(e) => setFilters({ ...filters, type: e.target.value })}
        >
          <option value="">Tous types</option>
          {TYPE_OPTIONS.filter(Boolean).map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        {hasFilters && (
          <button onClick={clearFilters} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600">
            <X size={12} /> Effacer
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="flex gap-3">
                <div className="h-5 w-16 bg-gray-200 rounded-full" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded-xs w-3/4" />
                  <div className="h-3 bg-gray-100 rounded-xs w-1/2" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : anomalies.length === 0 ? (
        <div className="card py-20 text-center">
          <CheckCircle size={48} className="mx-auto text-green-400 mb-4" />
          <p className="text-gray-500 font-medium">
            {showResolved ? 'Aucune anomalie résolue' : 'Aucune anomalie non résolue'}
          </p>
          {hasFilters && <p className="text-sm text-gray-400 mt-1">Essayez de modifier les filtres</p>}
        </div>
      ) : (
        <div className="space-y-6">
          {order.filter((s) => grouped[s]).map((severity) => (
            <div key={severity}>
              <div className="flex items-center gap-2 mb-3">
                <SeverityBadge severity={severity} />
                <span className="text-xs text-gray-400">{grouped[severity].length} anomalie{grouped[severity].length > 1 ? 's' : ''}</span>
              </div>
              <div className="card divide-y divide-gray-50">
                {grouped[severity].map((anomaly) => (
                  <AnomalyRow
                    key={anomaly.anomaly_id}
                    anomaly={anomaly}
                    onResolve={() => resolveMutation.mutate({ id: anomaly.anomaly_id })}
                    resolving={resolveMutation.isPending}
                    onViewDocument={setViewerDocId}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {viewerDocId && <DocumentViewer documentId={viewerDocId} onClose={() => setViewerDocId(null)} />}
    </div>
  )
}

function AnomalyRow({ anomaly, onResolve, resolving, onViewDocument }) {
  const [expanded, setExpanded] = useState(false)
  const { canResolveAnomaly } = usePermissions()

  const docId = anomaly.details?.document_id || anomaly.document_id

  return (
    <div className="px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span className="text-sm font-medium text-gray-800">{anomaly.message}</span>
            {anomaly.resolved && (
              <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">Résolue</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-400">
            {anomaly.supplier_name && <span className="font-medium text-gray-500">{anomaly.supplier_name}</span>}
            <span className="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-sm">{anomaly.type.replace(/_/g, ' ')}</span>
            <span>{formatDistanceToNow(new Date(anomaly.detected_at), { addSuffix: true, locale: fr })}</span>
            {anomaly.detected_at && (
              <span className="hidden sm:inline">{format(new Date(anomaly.detected_at), 'dd/MM/yyyy HH:mm')}</span>
            )}
          </div>
          {anomaly.details && Object.keys(anomaly.details).length > 0 && (
            <div className="mt-2 text-xs text-gray-400 bg-gray-50 rounded-xs px-2 py-1.5 font-mono">
              {Object.entries(anomaly.details).map(([k, v]) => (
                <span key={k} className="mr-3"><span className="text-gray-500">{k}:</span> {String(v)}</span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {docId && (
            <button
              onClick={() => onViewDocument(docId)}
              className="text-xs text-gray-600 hover:text-gray-900 font-medium px-2 py-1 flex items-center gap-1 rounded bg-gray-100 hover:bg-gray-200"
            >
              <Eye size={14} /> Document
            </button>
          )}
          {!anomaly.resolved && canResolveAnomaly && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-primary-600 hover:text-primary-700 font-medium px-2 py-1 rounded-xs border border-primary-200 hover:bg-primary-50"
            >
              {expanded ? 'Annuler' : 'Résoudre'}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => { onResolve(); setExpanded(false) }}
            disabled={resolving}
            className="btn-primary py-1.5 px-3 text-sm"
          >
            Confirmer la résolution
          </button>
          <button
            onClick={() => setExpanded(false)}
            className="btn-secondary py-1.5 px-3 text-sm"
          >
            Annuler
          </button>
        </div>
      )}
    </div>
  )
}
