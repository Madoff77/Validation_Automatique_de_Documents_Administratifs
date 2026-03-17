import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle, Clock, FileText, Calendar, ShieldAlert, Eye } from 'lucide-react'
import { suppliersApi, anomaliesApi } from '../api/index'
import DocumentViewer from '../components/DocumentViewer'
import { formatDistanceToNow, format } from 'date-fns'
import { fr } from 'date-fns/locale'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const STATUS_CONFIG = {
  compliant:     { label: 'Conforme',      icon: CheckCircle,  color: 'text-green-600', bg: 'bg-green-50',  border: 'border-green-200' },
  warning:       { label: 'Avertissement', icon: AlertTriangle, color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  non_compliant: { label: 'Non conforme',  icon: XCircle,       color: 'text-red-600',   bg: 'bg-red-50',    border: 'border-red-200' },
  pending:       { label: 'En attente',    icon: Clock,         color: 'text-gray-500',  bg: 'bg-gray-100',  border: 'border-gray-200' },
}

function ComplianceScore({ rate }) {
  const color = rate >= 80 ? 'text-green-600' : rate >= 50 ? 'text-yellow-600' : 'text-red-600'
  const trackColor = rate >= 80 ? 'bg-green-500' : rate >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', trackColor)} style={{ width: `${rate}%` }} />
      </div>
      <span className={clsx('text-sm font-bold w-10 text-right', color)}>{rate}%</span>
    </div>
  )
}

function SeverityBadge({ severity }) {
  const cfg = {
    error:   'bg-red-100 text-red-700',
    warning: 'bg-yellow-100 text-yellow-700',
    info:    'bg-blue-100 text-blue-600',
  }[severity] || 'bg-gray-100 text-gray-500'
  return <span className={`inline-flex text-xs font-semibold px-2 py-0.5 rounded-full ${cfg}`}>{severity}</span>
}

export default function SupplierCompliance() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [viewerDocId, setViewerDocId] = useState(null)

  const { data: supplier, isLoading: loadingSupplier } = useQuery({
    queryKey: ['supplier', id],
    queryFn: () => suppliersApi.get(id),
  })

  const { data: compliance } = useQuery({
    queryKey: ['supplier-compliance', id],
    queryFn: () => suppliersApi.compliance(id),
    enabled: !!id,
  })

  const { data: anomalies = [], isLoading: loadingAnomalies } = useQuery({
    queryKey: ['anomalies', { supplier_id: id }],
    queryFn: () => anomaliesApi.list({ supplier_id: id, limit: 50 }),
    enabled: !!id,
    refetchInterval: 20_000,
  })

  const resolveMutation = useMutation({
    mutationFn: ({ aId, notes }) => anomaliesApi.resolve(aId, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['anomalies', { supplier_id: id }] })
      qc.invalidateQueries({ queryKey: ['supplier', id] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      toast.success('Anomalie résolue')
    },
  })

  if (loadingSupplier) return (
    <div className="p-8 max-w-4xl mx-auto animate-pulse space-y-4">
      <div className="h-6 bg-gray-200 rounded w-48" />
      <div className="h-32 bg-gray-100 rounded-xl" />
    </div>
  )

  if (!supplier) return (
    <div className="p-8 text-center text-gray-500">Fournisseur introuvable</div>
  )

  const cfg = STATUS_CONFIG[supplier.compliance_status] || STATUS_CONFIG.pending
  const { icon: StatusIcon } = cfg

  const unresolvedAnomalies = anomalies.filter((a) => !a.resolved)
  const resolvedAnomalies = anomalies.filter((a) => a.resolved)

  const complianceRate = compliance
    ? Math.round(((compliance.total_documents - compliance.expired_documents) / Math.max(compliance.total_documents, 1)) * 100)
    : 0

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/suppliers" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft size={16} className="text-gray-500" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-gray-900">{supplier.name}</h1>
          {supplier.siret && (
            <p className="text-sm text-gray-500 font-mono">SIRET: {supplier.siret}</p>
          )}
        </div>
        <span className={clsx('inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full border', cfg.bg, cfg.color, cfg.border)}>
          <StatusIcon size={14} /> {cfg.label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Supplier info */}
        <div className="col-span-1 card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Informations</h2>
          {supplier.contact_email && (
            <div>
              <p className="text-xs text-gray-400">Email</p>
              <p className="text-sm text-gray-800">{supplier.contact_email}</p>
            </div>
          )}
          {supplier.contact_phone && (
            <div>
              <p className="text-xs text-gray-400">Téléphone</p>
              <p className="text-sm text-gray-800">{supplier.contact_phone}</p>
            </div>
          )}
          {supplier.address && (
            <div>
              <p className="text-xs text-gray-400">Adresse</p>
              <p className="text-sm text-gray-800">{supplier.address}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-400">Membre depuis</p>
            <p className="text-sm text-gray-800">
              {format(new Date(supplier.created_at), 'dd MMM yyyy', { locale: fr })}
            </p>
          </div>
        </div>

        {/* Compliance metrics */}
        <div className="col-span-2 card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Métriques de conformité</h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            {[
              { label: 'Documents totaux', value: compliance?.total_documents ?? '—', icon: FileText, color: 'text-blue-500' },
              { label: 'Expirations actives', value: compliance?.expired_documents ?? '—', icon: Calendar, color: 'text-red-500' },
              { label: 'Expire bientôt (30j)', value: compliance?.expiring_soon ?? '—', icon: Clock, color: 'text-yellow-500' },
              { label: 'Anomalies non résolues', value: unresolvedAnomalies.length, icon: ShieldAlert, color: 'text-orange-500' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="bg-gray-50 rounded-lg p-3 flex items-center gap-3">
                <Icon size={16} className={color} />
                <div>
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="text-lg font-bold text-gray-900">{value}</p>
                </div>
              </div>
            ))}
          </div>
          {compliance?.total_documents > 0 && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-gray-500">Taux de conformité documentaire</span>
              </div>
              <ComplianceScore rate={complianceRate} />
            </div>
          )}
        </div>
      </div>

      {/* Anomalies */}
      <div className="card">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <ShieldAlert size={16} className="text-orange-500" />
            Anomalies
            {unresolvedAnomalies.length > 0 && (
              <span className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
                {unresolvedAnomalies.length}
              </span>
            )}
          </h2>
          <span className="text-xs text-gray-400">{anomalies.length} au total</span>
        </div>

        {loadingAnomalies ? (
          <div className="px-6 py-8 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : anomalies.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <CheckCircle size={36} className="mx-auto text-green-400 mb-3" />
            <p className="text-sm text-gray-500">Aucune anomalie pour ce fournisseur</p>
          </div>
        ) : (
          <div>
            {unresolvedAnomalies.length > 0 && (
              <div className="divide-y divide-gray-50">
                {unresolvedAnomalies.map((a) => (
                  <AnomalyItem key={a.anomaly_id} anomaly={a} onResolve={(notes) => resolveMutation.mutate({ aId: a.anomaly_id, notes })} onViewDocument={setViewerDocId} />
                ))}
              </div>
            )}
            {resolvedAnomalies.length > 0 && (
              <details className="border-t border-gray-100">
                <summary className="px-6 py-3 text-xs text-gray-400 cursor-pointer hover:text-gray-600 list-none flex items-center gap-2">
                  <CheckCircle size={12} className="text-green-400" />
                  {resolvedAnomalies.length} anomalie{resolvedAnomalies.length > 1 ? 's' : ''} résolue{resolvedAnomalies.length > 1 ? 's' : ''}
                </summary>
                <div className="divide-y divide-gray-50">
                  {resolvedAnomalies.map((a) => (
                    <AnomalyItem key={a.anomaly_id} anomaly={a} resolved onViewDocument={setViewerDocId} />
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>
      {viewerDocId && <DocumentViewer documentId={viewerDocId} onClose={() => setViewerDocId(null)} />}
    </div>
  )
}

function AnomalyItem({ anomaly, onResolve, resolved, onViewDocument }) {
  const [expanded, setExpanded] = useState(false)
  const [notes, setNotes] = useState('')

  const docId = anomaly.details?.document_id || anomaly.document_id

  return (
    <div className={clsx('px-6 py-4', resolved && 'opacity-60')}>
      <div className="flex items-start gap-3">
        <SeverityBadge severity={anomaly.severity} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-800">{anomaly.message}</p>
          <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
            <span className="bg-gray-100 px-1.5 py-0.5 rounded">{anomaly.type.replace(/_/g, ' ')}</span>
            <span>{formatDistanceToNow(new Date(anomaly.detected_at), { addSuffix: true, locale: fr })}</span>
            {resolved && anomaly.resolved_at && (
              <span className="text-green-500">
                Résolue {formatDistanceToNow(new Date(anomaly.resolved_at), { addSuffix: true, locale: fr })}
              </span>
            )}
          </div>
          {anomaly.details && Object.keys(anomaly.details).length > 0 && (
            <div className="mt-1.5 text-xs font-mono text-gray-400 bg-gray-50 rounded px-2 py-1">
              {Object.entries(anomaly.details).map(([k, v]) => (
                <span key={k} className="mr-3"><span className="text-gray-500">{k}:</span> {String(v)}</span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {docId && (
            <button
              onClick={() => onViewDocument(docId)}
              className="text-xs text-gray-600 hover:text-gray-900 font-medium px-2 py-1 flex items-center gap-1 rounded bg-gray-100 hover:bg-gray-200"
            >
              <Eye size={14} /> Doc
            </button>
          )}
          {!resolved && onResolve && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-primary-600 hover:text-primary-700 font-medium px-2 py-1 rounded border border-primary-200 hover:bg-primary-50 flex-shrink-0"
            >
              {expanded ? 'Annuler' : 'Résoudre'}
            </button>
          )}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 flex gap-2 ml-16">
          <input
            className="input flex-1 py-1.5 text-sm"
            placeholder="Notes (optionnel)…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <button
            onClick={() => { onResolve(notes); setExpanded(false) }}
            className="btn-primary py-1.5 px-3 text-sm"
          >
            Confirmer
          </button>
        </div>
      )}
    </div>
  )
}
