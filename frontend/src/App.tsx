import { useEffect, useState } from 'react'

type Health = { status: string; elasticsearch: string }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'down', elasticsearch: 'unknown' }))
  }, [])

  return (
    <main style={{ padding: 24 }}>
      <h1>Confox</h1>
      <p style={{ color: 'var(--muted)' }}>
        API: {health?.status ?? '…'} · Elasticsearch: {health?.elasticsearch ?? '…'}
      </p>
    </main>
  )
}
