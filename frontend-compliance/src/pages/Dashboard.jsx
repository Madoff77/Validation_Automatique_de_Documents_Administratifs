import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, XCircle, CheckCircle, Clock, Users, TrendingUp, Calendar, ShieldAlert } from 'lucide-react'
import { statsApi, anomaliesApi, suppliersApi } from '../api/index'
import { formatDistanceToNow } from 'date-fns'
import { fr } from 'date-fns/locale'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const SEVERITY_COLORS = { error: '#ef4444', warning: '#f59e0b', info: '#3b82f6' }
const COMPLIANCE_COLORS = {
  compliant: '#22c55e', warning: '#f59e0b', non_compliant: '#ef4444', pending: '#94a3b8'
}

function StatCard({ icon: Icon, label, value, sub, color, loading }) {
  const colors = {
    red: 'bg-red-50 text-red-600', orange: 'bg-orange-50 text-orange-600',
    green: 'bg-green-50 text-green-600', blue: 'bg-blue-50 text-blue-600',
    gray: 'bg-gray-100 text-gray-500',
  }
  return (
    <div className="card p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg ${colors[color] || colors.gray}`}><Icon size={20} /></div>
      <div className="flex-1">
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        {loading
          ? <div className="h-7 w-16 bg-gray-200 rounded-xs animate-pulse mt-1" />
          : <p className="text-2xl font-bold text-gray-900">{value ?? '—'}</p>
        }
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function SeverityBadge({ severity }) {
  const cfg = {
    error:   'bg-red-100 text-red-700',
    warning: 'bg-yellow-100 text-yellow-700',
    info:    'bg-blue-100 text-blue-600',
  }[severity] || 'bg-gray-100 text-gray-500'
  return <span className={`inline-flex text-xs font-medium px-2 py-0.5 rounded-full ${cfg}`}>{severity}</span>
}

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'], queryFn: statsApi.dashboard, refetchInterval: 15_000
  })
  const { data: recentAnomalies = [] } = useQuery({
    queryKey: ['anomalies', { resolved: false, limit: 8 }],
    queryFn: () => anomaliesApi.list({ resolved: false, limit: 8 }),
  })
  const { data: suppliers = [] } = useQuery({
    queryKey: ['suppliers'], queryFn: () => suppliersApi.list({ limit: 100 }),
  })

  // Données pour le graphique compliance
  const complianceCounts = suppliers.reduce((acc, s) => {
    acc[s.compliance_status] = (acc[s.compliance_status] || 0) + 1
    return acc
  }, {})
  const pieData = Object.entries(complianceCounts).map(([name, value]) => ({ name, value }))

  const complianceRate = suppliers.length > 0
    ? Math.round((complianceCounts.compliant || 0) / suppliers.length * 100)
    : 0

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tableau de bord Conformité</h1>
          <p className="text-sm text-gray-500 mt-0.5">Vue d'ensemble des risques et anomalies</p>
        </div>
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
          <div className={`w-2.5 h-2.5 rounded-full ${complianceRate >= 80 ? 'bg-green-500' : complianceRate >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`} />
          <span className="text-sm font-semibold text-gray-700">{complianceRate}% conformes</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={XCircle}      label="Anomalies critiques"  value={stats?.critical_anomalies}   color="red"    loading={isLoading} sub="erreurs bloquantes" />
        <StatCard icon={AlertTriangle} label="Non résolues"        value={stats?.unresolved_anomalies} color="orange" loading={isLoading} />
        <StatCard icon={Calendar}     label="Expire bientôt"      value={stats?.documents_expiring_soon} color="orange" loading={isLoading} sub="< 30 jours" />
        <StatCard icon={CheckCircle}  label="Fournisseurs conformes" value={complianceCounts.compliant || 0} color="green" loading={isLoading} sub={`sur ${suppliers.length}`} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Anomalies récentes */}
        <div className="col-span-2 card">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <ShieldAlert size={16} className="text-orange-500" />
              Anomalies non résolues
            </h2>
            <Link to="/anomalies" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
              Voir tout →
            </Link>
          </div>
          {recentAnomalies.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <CheckCircle size={36} className="mx-auto text-green-400 mb-3" />
              <p className="text-sm text-gray-500">Aucune anomalie non résolue</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {recentAnomalies.map((a) => (
                <div key={a.anomaly_id} className="px-6 py-3.5 flex items-start gap-3">
                  <SeverityBadge severity={a.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{a.message}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {a.supplier_name && <span className="font-medium">{a.supplier_name} · </span>}
                      {formatDistanceToNow(new Date(a.detected_at), { addSuffix: true, locale: fr })}
                    </p>
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap">{a.type.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Graphique conformité */}
        <div className="card p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Conformité fournisseurs</h2>
          {suppliers.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Aucun fournisseur</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                     paddingAngle={3} dataKey="value">
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={COMPLIANCE_COLORS[entry.name] || '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} />
                <Legend iconType="circle" iconSize={8} formatter={(v) => <span className="text-xs capitalize">{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="mt-2 space-y-1.5">
            {Object.entries(complianceCounts).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: COMPLIANCE_COLORS[status] }} />
                  <span className="text-gray-600 capitalize">{status.replace('_', ' ')}</span>
                </div>
                <span className="font-semibold text-gray-800">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
