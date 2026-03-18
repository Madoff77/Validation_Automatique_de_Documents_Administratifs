import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Users, Search, CheckCircle, XCircle, AlertTriangle, Clock, ChevronRight } from 'lucide-react'
import { suppliersApi } from '../api/index'
import clsx from 'clsx'

const STATUS_CONFIG = {
  compliant:     { label: 'Conforme',      icon: CheckCircle,  color: 'text-green-600',  bg: 'bg-green-100',  border: 'border-green-200' },
  warning:       { label: 'Avertissement', icon: AlertTriangle, color: 'text-yellow-600', bg: 'bg-yellow-100', border: 'border-yellow-200' },
  non_compliant: { label: 'Non conforme',  icon: XCircle,       color: 'text-red-600',    bg: 'bg-red-100',    border: 'border-red-200' },
  pending:       { label: 'En attente',    icon: Clock,         color: 'text-gray-500',   bg: 'bg-gray-100',   border: 'border-gray-200' },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending
  const { icon: Icon } = cfg
  return (
    <span className={clsx('inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full border', cfg.bg, cfg.color, cfg.border)}>
      <Icon size={11} />
      {cfg.label}
    </span>
  )
}

export default function Suppliers() {
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const { data: suppliers = [], isLoading } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => suppliersApi.list({ limit: 200 }),
    refetchInterval: 30_000,
  })

  const filtered = suppliers.filter((s) => {
    const matchSearch = !search || s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.siret?.includes(search)
    const matchStatus = !filterStatus || s.compliance_status === filterStatus
    return matchSearch && matchStatus
  })

  const counts = suppliers.reduce((acc, s) => {
    acc[s.compliance_status] = (acc[s.compliance_status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fournisseurs</h1>
          <p className="text-sm text-gray-500 mt-0.5">{suppliers.length} fournisseur{suppliers.length > 1 ? 's' : ''} enregistrés</p>
        </div>
      </div>

      {/* Status summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {Object.entries(STATUS_CONFIG).map(([status, cfg]) => {
          const { icon: Icon } = cfg
          return (
            <button
              key={status}
              onClick={() => setFilterStatus(filterStatus === status ? '' : status)}
              className={clsx(
                'card p-4 flex items-center gap-3 text-left transition-all',
                filterStatus === status ? `ring-2 ring-offset-1 ${cfg.border}` : 'hover:shadow-xs-md'
              )}
            >
              <div className={clsx('p-2 rounded-lg', cfg.bg)}>
                <Icon size={16} className={cfg.color} />
              </div>
              <div>
                <p className="text-xs text-gray-500">{cfg.label}</p>
                <p className="text-xl font-bold text-gray-900">{counts[status] || 0}</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Search + filter bar */}
      <div className="card p-4 mb-6 flex items-center gap-3">
        <Search size={16} className="text-gray-400 shrink-0" />
        <input
          className="flex-1 text-sm outline-hidden bg-transparent placeholder-gray-400"
          placeholder="Rechercher par nom ou SIRET…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {(search || filterStatus) && (
          <button
            onClick={() => { setSearch(''); setFilterStatus('') }}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            Effacer
          </button>
        )}
      </div>

      {/* Supplier list */}
      {isLoading ? (
        <div className="card divide-y divide-gray-50">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="px-5 py-4 flex items-center gap-4 animate-pulse">
              <div className="w-10 h-10 bg-gray-200 rounded-xl" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-200 rounded-xs w-1/3" />
                <div className="h-3 bg-gray-100 rounded-xs w-1/4" />
              </div>
              <div className="h-6 w-24 bg-gray-200 rounded-full" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card py-16 text-center">
          <Users size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">Aucun fournisseur trouvé</p>
        </div>
      ) : (
        <div className="card divide-y divide-gray-50">
          {filtered.map((supplier) => (
            <Link
              key={supplier.supplier_id}
              to={`/suppliers/${supplier.supplier_id}`}
              className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors group"
            >
              <div className="w-10 h-10 bg-gray-100 rounded-xl flex items-center justify-center text-gray-500 font-semibold text-sm shrink-0 group-hover:bg-primary-50 group-hover:text-primary-600 transition-colors">
                {supplier.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{supplier.name}</p>
                <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                  {supplier.siret && <span className="font-mono">{supplier.siret}</span>}
                  {supplier.contact_email && <span>{supplier.contact_email}</span>}
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {supplier.active_anomalies_count > 0 && (
                  <span className="text-xs bg-red-100 text-red-600 font-semibold px-2 py-0.5 rounded-full">
                    {supplier.active_anomalies_count} anomalie{supplier.active_anomalies_count > 1 ? 's' : ''}
                  </span>
                )}
                <StatusBadge status={supplier.compliance_status} />
                <ChevronRight size={14} className="text-gray-300 group-hover:text-gray-500 transition-colors" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
