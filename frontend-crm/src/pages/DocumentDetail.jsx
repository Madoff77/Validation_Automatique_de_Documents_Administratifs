import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, RefreshCw, Download, AlertTriangle, CheckCircle,
  Info, Loader2, FileText, Building2, Calendar, CreditCard, Euro,
} from 'lucide-react'
import { documentsApi } from '../api/documents'
import { DocStatusBadge, DocTypeBadge, ValidationBadge } from '../components/StatusBadge'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

function FieldRow({ icon: Icon, label, value, highlight }) {
  if (!value) return null
  return (
    <div className={`flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0
                     ${highlight ? 'bg-yellow-50 -mx-5 px-5 rounded' : ''}`}>
      <div className="mt-0.5">
        {Icon ? <Icon size={14} className="text-gray-400" /> : <div className="w-3.5" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <p className="text-sm text-gray-900 font-medium">{value}</p>
      </div>
    </div>
  )
}

function CheckRow({ check }) {
  const icon = check.status === 'ok'
    ? <CheckCircle size={15} className="text-green-500 flex-shrink-0" />
    : check.status === 'warning'
      ? <AlertTriangle size={15} className="text-yellow-500 flex-shrink-0" />
      : <AlertTriangle size={15} className="text-red-500 flex-shrink-0" />
  return (
    <div className="flex items-start gap-2.5 py-2 border-b border-gray-50 last:border-0">
      {icon}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{check.rule}</p>
        <p className="text-sm text-gray-800 mt-0.5">{check.message}</p>
      </div>
    </div>
  )
}

const formatAmount = (v) => v != null ? `${v.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} €` : null

export default function DocumentDetail() {
  const { id } = useParams()
  const qc = useQueryClient()

  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsApi.get(id),
    refetchInterval: (data) =>
      data && ['processed', 'error'].includes(data.status) ? false : 8_000,
  })

  const reprocessMutation = useMutation({
    mutationFn: () => documentsApi.reprocess(id),
    onSuccess: () => {
      qc.invalidateQueries(['document', id])
      toast.success('Retraitement lancé')
    },
  })

  if (isLoading) return (
    <div className="p-8 flex items-center gap-3 text-gray-500">
      <Loader2 size={20} className="animate-spin" /> Chargement…
    </div>
  )

  if (!doc) return <div className="p-8 text-gray-500">Document introuvable.</div>

  const ext = doc.extracted || {}
  const validation = doc.validation || {}
  const checks = validation.checks || []
  const isProcessed = doc.status === 'processed'
  const isError = doc.status === 'error'
  const inProgress = !isProcessed && !isError

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link to="/documents" className="inline-flex items-center gap-1.5 text-sm text-gray-500
                                        hover:text-gray-700 mb-6 transition-colors">
        <ArrowLeft size={15} /> Documents
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <FileText size={24} className="text-gray-500" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 max-w-xl">{doc.original_filename}</h1>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {doc.doc_type && <DocTypeBadge type={doc.doc_type} />}
              <DocStatusBadge status={doc.status} />
              {validation.status && <ValidationBadge status={validation.status} />}
              {doc.classification_confidence && (
                <span className="text-xs text-gray-400">
                  confiance : {(doc.classification_confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isError && (
            <button onClick={() => reprocessMutation.mutate()} className="btn-secondary">
              {reprocessMutation.isPending
                ? <Loader2 size={15} className="animate-spin" />
                : <RefreshCw size={15} />
              }
              Relancer
            </button>
          )}
          <a
            href={documentsApi.getDownloadUrl(id)}
            target="_blank" rel="noopener noreferrer"
            className="btn-secondary"
          >
            <Download size={15} /> Télécharger
          </a>
        </div>
      </div>

      {/* Barre de progression */}
      {inProgress && (
        <div className="card p-4 mb-6 flex items-center gap-3 bg-blue-50 border-blue-100">
          <Loader2 size={18} className="text-blue-500 animate-spin flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-800">Traitement en cours…</p>
            <p className="text-xs text-blue-600 mt-0.5">
              Statut actuel : <strong>{doc.status}</strong>
              {doc.airflow_run_id && ` · Run Airflow : ${doc.airflow_run_id}`}
            </p>
          </div>
        </div>
      )}

      {isError && doc.error_message && (
        <div className="card p-4 mb-6 flex items-start gap-3 bg-red-50 border-red-100">
          <AlertTriangle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">Erreur de traitement</p>
            <p className="text-xs text-red-600 mt-0.5 font-mono">{doc.error_message}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Champs extraits */}
        <div className="col-span-2 space-y-5">
          {isProcessed && Object.keys(ext).length > 0 ? (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Info size={16} className="text-primary-600" />
                Données extraites
              </h2>
              <div className="space-y-0.5">
                <FieldRow icon={Building2} label="Raison sociale"    value={ext.raison_sociale} />
                <FieldRow icon={Building2} label="SIRET"             value={ext.siret} />
                <FieldRow icon={Building2} label="SIREN"             value={ext.siren} />
                <FieldRow icon={Building2} label="N° TVA"            value={ext.tva_number} />
                <FieldRow icon={Euro}      label="Montant HT"        value={formatAmount(ext.montant_ht)} />
                <FieldRow icon={Euro}      label="Montant TVA"       value={formatAmount(ext.montant_tva)} />
                <FieldRow icon={Euro}      label="Montant TTC"       value={formatAmount(ext.montant_ttc)} highlight={!!ext.montant_ttc} />
                <FieldRow icon={null}      label="Taux TVA"          value={ext.taux_tva ? `${ext.taux_tva} %` : null} />
                <FieldRow icon={Calendar}  label="Date d'émission"   value={ext.date_emission} />
                <FieldRow icon={Calendar}  label="Date d'échéance"   value={ext.date_echeance} />
                <FieldRow icon={Calendar}  label="Date d'expiration" value={ext.date_expiration}
                           highlight={!!ext.date_expiration} />
                <FieldRow icon={null}      label="N° document"       value={ext.numero_document} />
                <FieldRow icon={CreditCard} label="IBAN"             value={ext.iban} />
                <FieldRow icon={CreditCard} label="BIC"              value={ext.bic} />
                <FieldRow icon={null}      label="Banque"            value={ext.banque} />
                <FieldRow icon={null}      label="Adresse"           value={ext.adresse} />
              </div>
            </div>
          ) : isProcessed ? (
            <div className="card p-8 text-center text-gray-400">
              <Info size={28} className="mx-auto mb-2 text-gray-300" />
              <p className="text-sm">Aucune donnée extraite pour ce document.</p>
            </div>
          ) : null}

          {/* Vérifications */}
          {checks.length > 0 && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <CheckCircle size={16} className="text-green-600" />
                Résultats de validation
                <ValidationBadge status={validation.status} />
              </h2>
              <div className="space-y-0.5">
                {checks.map((c, i) => <CheckRow key={i} check={c} />)}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Informations</h3>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-xs text-gray-400 block">Fournisseur</span>
                <Link to={`/suppliers/${doc.supplier_id}`}
                      className="text-primary-600 hover:underline text-sm">
                  Voir le fournisseur →
                </Link>
              </div>
              <div>
                <span className="text-xs text-gray-400 block">Type MIME</span>
                <span className="text-gray-700">{doc.mime_type}</span>
              </div>
              <div>
                <span className="text-xs text-gray-400 block">Taille</span>
                <span className="text-gray-700">{(doc.file_size_bytes / 1024).toFixed(0)} Ko</span>
              </div>
              <div>
                <span className="text-xs text-gray-400 block">Importé le</span>
                <span className="text-gray-700">{format(new Date(doc.upload_timestamp), 'dd/MM/yyyy HH:mm')}</span>
              </div>
              {doc.processing_duration_ms && (
                <div>
                  <span className="text-xs text-gray-400 block">Durée traitement</span>
                  <span className="text-gray-700">{(doc.processing_duration_ms / 1000).toFixed(1)}s</span>
                </div>
              )}
              {doc.ocr_quality_score && (
                <div>
                  <span className="text-xs text-gray-400 block">Qualité OCR</span>
                  <span className="text-gray-700">{(doc.ocr_quality_score * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          </div>

          {doc.airflow_run_id && (
            <div className="card p-4">
              <p className="text-xs text-gray-400 font-medium mb-1">Run Airflow</p>
              <p className="text-xs text-gray-600 font-mono break-all">{doc.airflow_run_id}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
