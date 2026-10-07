import { useEffect, useState } from 'react'

export const Tag = ({ tone = '', children }) => <span className={`tag ${tone}`}>{children}</span>
export const Empty = ({ children }) => <div className="empty">{children}</div>
export const ErrorBanner = ({ error, onClose }) =>
  error ? <div className="banner" role="alert"><span>{error}</span><button className="btn sm" onClick={onClose}>Dismiss</button></div> : null

// Runs an async action, tracking busy state and surfacing errors through the shared banner.
export function useAction(onError) {
  const [busy, setBusy] = useState(false)
  const run = async (fn) => {
    setBusy(true)
    try { return await fn() } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  return [busy, run]
}

export function useDebounced(value, ms = 250) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}
