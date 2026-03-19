import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, Download, Building2, Calendar, CreditCard, Euro, FileText, Loader2 } from 'lucide-react'
import { documentsApi } from '../api'
import apiClient from '../api/client'

const formatAmount = (v) => v != null ? `${v.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} €` : 'N/A'

function FieldRow({ icon: Icon, label, value }) {
  if (!value) return null
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className="mt-0.5">
        {Icon ? <Icon size={16} className="text-muted-foreground" /> : <div className="w-4" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-sm text-foreground font-semibold">{value}</p>
      </div>
    </div>
  )
}

function SkeletonField() {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0 animate-pulse">
      <div className="w-4 h-4 bg-muted rounded mt-0.5" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-muted rounded w-1/3" />
        <div className="h-4 bg-muted rounded w-2/3" />
      </div>
    </div>
  )
}

export default function DocumentViewer({ documentId, onClose }) {
  const [iframeLoaded, setIframeLoaded] = useState(false)

  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => documentsApi.get(documentId),
    enabled: !!documentId,
  })

  // Endpoints définis par le backend
  const viewUrl = `${apiClient.defaults.baseURL}/documents/${documentId}/view`
  const downloadUrl = `${apiClient.defaults.baseURL}/documents/${documentId}/download`

  const ext = doc?.extracted || {}

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="bg-card rounded-2xl shadow-2xl flex flex-col w-full max-w-6xl h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/40">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/15 rounded-lg">
              <FileText size={20} className="text-primary" />
            </div>
            <div>
              <h2 className="font-bold text-foreground text-lg">
                {doc?.original_filename || 'Visualisation du document'}
              </h2>
              <p className="text-xs text-muted-foreground font-mono">ID: {documentId}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-primary hover:bg-primary/90 text-primary-foreground py-2 px-4 rounded-lg inline-flex items-center gap-2 text-sm font-medium transition-colors"
            >
              <Download size={16} />
              Télécharger l'original
            </a>
            <button onClick={onClose} className="p-2 rounded-xl border border-border hover:bg-muted transition-colors text-muted-foreground">
              <X size={20} />
            </button>
          </div>
        </div>
        <div className="flex flex-1 overflow-hidden min-h-0">
          <div className="flex-1 bg-muted relative border-r border-border flex items-center justify-center">
            {!iframeLoaded && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground bg-muted z-10">
                <Loader2 size={32} className="animate-spin mb-4 text-primary" />
                <p className="font-medium">Chargement du document...</p>
              </div>
            )}
            <iframe
              src={viewUrl}
              title="Document Viewer"
              className={`w-full h-full border-0 transition-opacity duration-300 ${iframeLoaded ? 'opacity-100' : 'opacity-0'}`}
              onLoad={() => setIframeLoaded(true)}
            />
          </div>
          <div className="w-96 bg-card overflow-y-auto">
            <div className="p-6">
              <h3 className="text-sm font-bold text-foreground uppercase tracking-wider mb-6 border-b border-border pb-2">
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
                  <FieldRow icon={Building2} label="Raison sociale" value={ext.raison_sociale} />
                  <FieldRow icon={Building2} label="SIRET" value={ext.siret} />
                  <FieldRow icon={Building2} label="SIREN" value={ext.siren} />
                  <FieldRow icon={Building2} label="N° TVA" value={ext.tva_number} />
                  <FieldRow icon={Euro} label="Montant HT" value={ext.montant_ht ? formatAmount(ext.montant_ht) : null} />
                  <FieldRow icon={Euro} label="Montant TVA" value={ext.montant_tva ? formatAmount(ext.montant_tva) : null} />
                  <FieldRow icon={Euro} label="Montant TTC" value={ext.montant_ttc ? formatAmount(ext.montant_ttc) : null} />
                  <FieldRow icon={Calendar} label="Date d'émission" value={ext.date_emission} />
                  <FieldRow icon={Calendar} label="Date d'échéance" value={ext.date_echeance} />
                  <FieldRow icon={CreditCard} label="IBAN" value={ext.iban} />
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText size={32} className="mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm">Aucune donnée extraite ou en cours de traitement.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
