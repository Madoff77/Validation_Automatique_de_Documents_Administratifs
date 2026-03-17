import { useAuth } from '../contexts/AuthContext'

/**
 * Source unique des permissions frontend.
 * Le backend reste la source de vérité sécurité.
 * Ce hook sert uniquement à adapter l'UX selon le rôle.
 */
export function usePermissions() {
  const { user } = useAuth()
  const role = user?.role

  return {
    // Actions d'écriture — operator + admin
    canUpload: role === 'admin' || role === 'operator',
    canCreateSupplier: role === 'admin' || role === 'operator',
    canEditSupplier: role === 'admin' || role === 'operator',
    canReprocess: role === 'admin' || role === 'operator',

    // Admin uniquement
    isAdmin: role === 'admin',

    // Lecture seule
    isViewer: role === 'viewer',
  }
}
