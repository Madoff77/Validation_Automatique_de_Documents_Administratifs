import { useQuery } from '@tanstack/react-query'
import { Calendar, AlertTriangle, XCircle, CheckCircle, Clock } from 'lucide-react'
import { anomaliesApi } from '../api/index'
import { format, differenceInDays, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'
import clsx from 'clsx'

function urgencyConfig(daysLeft) {
  if (daysLeft < 0)  return { label: 'Expiré',        color: 'text-red-700',    bg: 'bg-red-50',    border: 'border-red-200',    icon: XCircle,      iconColor: 'text-red-500' }
  if (daysLeft <= 7) return { label: 'Critique',       color: 'text-red-600',    bg: 'bg-red-50',    border: 'border-red-200',    icon: XCircle,      iconColor: 'text-red-400' }
  if (daysLeft <= 14) return { label: 'Urgent',        color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200', icon: AlertTriangle, iconColor: 'text-orange-400' }
  if (daysLeft <= 30) return { label: 'Attention',     color: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200', icon: Clock,        iconColor: 'text-yellow-500' }
  return             { label: 'OK',             color: 'text-green-700',  bg: 'bg-green-50',  border: 'border-green-200',  icon: CheckCircle,  iconColor: 'text-green-400' }
}

function ExpirationRow({ anomaly }) {
  const expDate = anomaly.details?.expiration_date || anomaly.details?.expiry_date
  const daysLeft = expDate ? differenceInDays(parseISO(expDate), new Date()) : null
  const cfg = daysLeft !== null ? urgencyConfig(daysLeft) : urgencyConfig(999)
  const { icon: Icon } = cfg

  return (
    <div className={clsx('flex items-center gap-4 px-5 py-4 border-l-4', cfg.border)}>
      <Icon size={18} className={cfg.iconColor} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{anomaly.message}</p>
        <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
          {anomaly.supplier_name && <span className="font-medium text-gray-500">{anomaly.supplier_name}</span>}
          <span className="bg-gray-100 px-1.5 py-0.5 rounded-sm">{anomaly.type.replace(/_/g, ' ')}</span>
        </div>
      </div>
      <div className="text-right shrink-0">
        {expDate && (
          <p className="text-sm font-semibold text-gray-700">
            {format(parseISO(expDate), 'dd MMM yyyy', { locale: fr })}
          </p>
        )}
        {daysLeft !== null && (
          <p className={clsx('text-xs font-bold mt-0.5', cfg.color)}>
            {daysLeft < 0
              ? `Expiré il y a ${Math.abs(daysLeft)}j`
              : daysLeft === 0 ? "Expire aujourd'hui"
              : `J-${daysLeft}`
            }
          </p>
        )}
      </div>
      <span className={clsx('text-xs font-semibold px-2 py-0.5 rounded-full', cfg.bg, cfg.color)}>
        {cfg.label}
      </span>
    </div>
  )
}

export default function Expirations() {
  const { data: expirations = [], isLoading } = useQuery({
    queryKey: ['expirations'],
    queryFn: anomaliesApi.expiringSoon,
    refetchInterval: 60_000,
  })

  const grouped = expirations.reduce((acc, a) => {
    const expDate = a.details?.expiration_date || a.details?.expiry_date
    const daysLeft = expDate ? differenceInDays(parseISO(expDate), new Date()) : 999
    const bucket =
      daysLeft < 0    ? 'expired' :
      daysLeft <= 7   ? 'critical' :
      daysLeft <= 14  ? 'urgent' :
                        'warning'
    if (!acc[bucket]) acc[bucket] = []
    acc[bucket].push({ ...a, _daysLeft: daysLeft })
    return acc
  }, {})

  const sections = [
    { key: 'expired',  label: 'Documents expirés',           icon: XCircle,       iconColor: 'text-red-500' },
    { key: 'critical', label: 'Expire dans 7 jours',         icon: AlertTriangle, iconColor: 'text-red-400' },
    { key: 'urgent',   label: 'Expire dans 14 jours',        icon: AlertTriangle, iconColor: 'text-orange-400' },
    { key: 'warning',  label: 'Expire dans 30 jours',        icon: Clock,         iconColor: 'text-yellow-500' },
  ]

  const total = expirations.length

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-prata text-2xl font-bold text-gray-900">Expirations</h1>
          <p className="text-sm text-gray-500 mt-0.5">Documents à renouveler prochainement</p>
        </div>
        {total > 0 && (
          <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-xl px-4 py-2">
            <Calendar size={16} className="text-orange-500" />
            <span className="text-sm font-semibold text-orange-700">{total} document{total > 1 ? 's' : ''} à surveiller</span>
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {sections.map(({ key, label, icon: Icon, iconColor }) => (
          <div key={key} className="card p-4 flex items-center gap-3">
            <Icon size={20} className={iconColor} />
            <div>
              <p className="text-xs text-gray-500">{label.split(' ').slice(0, 2).join(' ')}</p>
              <p className="text-2xl font-bold text-gray-900">{grouped[key]?.length || 0}</p>
            </div>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="flex gap-3">
                <div className="w-4 h-4 bg-gray-200 rounded-full mt-0.5" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded-xs w-2/3" />
                  <div className="h-3 bg-gray-100 rounded-xs w-1/3" />
                </div>
                <div className="h-4 w-16 bg-gray-200 rounded-sm" />
              </div>
            </div>
          ))}
        </div>
      ) : total === 0 ? (
        <div className="card py-20 text-center">
          <CheckCircle size={48} className="mx-auto text-green-400 mb-4" />
          <p className="text-gray-500 font-medium">Aucun document n'expire dans les 30 prochains jours</p>
          <p className="text-sm text-gray-400 mt-1">Tous les documents sont à jour</p>
        </div>
      ) : (
        <div className="space-y-6">
          {sections.filter(({ key }) => grouped[key]?.length > 0).map(({ key, label, icon: Icon, iconColor }) => (
            <div key={key}>
              <div className="flex items-center gap-2 mb-3">
                <Icon size={15} className={iconColor} />
                <span className="text-sm font-semibold text-gray-700">{label}</span>
                <span className="text-xs text-gray-400">({grouped[key].length})</span>
              </div>
              <div className="card overflow-hidden divide-y divide-gray-50">
                {grouped[key]
                  .sort((a, b) => a._daysLeft - b._daysLeft)
                  .map((a) => <ExpirationRow key={a.anomaly_id} anomaly={a} />)
                }
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
