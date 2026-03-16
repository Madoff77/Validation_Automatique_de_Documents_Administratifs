import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Building2, ChevronRight, Loader2, X } from 'lucide-react'
import { suppliersApi } from '../api/suppliers'
import { ComplianceBadge } from '../components/StatusBadge'
import { usePermissions } from '../hooks/usePermissions'
import toast from 'react-hot-toast'

function CreateModal({ onClose }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', siret: '', email: '', phone: '', address: '' })

  const mutation = useMutation({
    mutationFn: suppliersApi.create,
    onSuccess: (data) => {
      qc.invalidateQueries(['suppliers'])
      toast.success(`Fournisseur ${data.name} créé`)
      navigate(`/suppliers/${data.supplier_id}`)
      onClose()
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Erreur lors de la création'),
  })

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-900">Nouveau fournisseur</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mutation.mutate(form) }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="label">Raison sociale *</label>
            <input className="input" value={form.name} onChange={set('name')} required placeholder="ACME SAS" />
          </div>
          <div>
            <label className="label">SIRET</label>
            <input className="input" value={form.siret} onChange={set('siret')} placeholder="73282932000074"
                   pattern="\d{14}" title="14 chiffres" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" value={form.email} onChange={set('email')} />
            </div>
            <div>
              <label className="label">Téléphone</label>
              <input className="input" value={form.phone} onChange={set('phone')} />
            </div>
          </div>
          <div>
            <label className="label">Adresse</label>
            <input className="input" value={form.address} onChange={set('address')} />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">
              Annuler
            </button>
            <button type="submit" className="btn-primary flex-1 justify-center" disabled={mutation.isPending}>
              {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : null}
              Créer
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Suppliers() {
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const { canCreateSupplier } = usePermissions()

  const { data: suppliers = [], isLoading } = useQuery({
    queryKey: ['suppliers', search],
    queryFn: () => suppliersApi.list({ search: search || undefined }),
  })

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fournisseurs</h1>
          <p className="text-sm text-gray-500 mt-0.5">{suppliers.length} fournisseur{suppliers.length > 1 ? 's' : ''}</p>
        </div>
        {canCreateSupplier && (
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Plus size={16} /> Nouveau fournisseur
          </button>
        )}
      </div>

      {/* Recherche */}
      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9 max-w-sm"
          placeholder="Rechercher par nom ou SIRET…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Liste */}
      <div className="card divide-y divide-gray-50">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-6 py-4 animate-pulse">
              <div className="w-10 h-10 bg-gray-200 rounded-lg" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-48 bg-gray-200 rounded" />
                <div className="h-3 w-32 bg-gray-200 rounded" />
              </div>
            </div>
          ))
        ) : suppliers.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Building2 size={40} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 text-sm">Aucun fournisseur trouvé</p>
          </div>
        ) : (
          suppliers.map((s) => (
            <Link
              key={s.supplier_id}
              to={`/suppliers/${s.supplier_id}`}
              className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors group"
            >
              <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Building2 size={20} className="text-primary-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{s.name}</p>
                <p className="text-sm text-gray-400">
                  {s.siret ? `SIRET : ${s.siret}` : 'SIRET non renseigné'}
                  {s.email ? ` · ${s.email}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className="text-xs text-gray-400">{s.document_count} doc{s.document_count > 1 ? 's' : ''}</span>
                <ComplianceBadge status={s.compliance_status} />
                <ChevronRight size={16} className="text-gray-300 group-hover:text-gray-500 transition-colors" />
              </div>
            </Link>
          ))
        )}
      </div>

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} />}
    </div>
  )
}
