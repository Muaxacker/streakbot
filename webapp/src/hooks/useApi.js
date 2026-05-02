import { useState, useEffect } from 'react'

const BASE = import.meta.env.VITE_API_URL || '/api'

// Headers needed to bypass ngrok browser warning page
const HEADERS = {
  'ngrok-skip-browser-warning': 'true',
  'Content-Type': 'application/json',
}

export function useApi(endpoint) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(`${BASE}${endpoint}`, { headers: HEADERS })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false) } })

    return () => { cancelled = true }
  }, [endpoint])

  const refetch = () => {
    setLoading(true)
    fetch(`${BASE}${endpoint}`, { headers: HEADERS })
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  return { data, loading, error, refetch }
}
