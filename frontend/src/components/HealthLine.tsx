import { useEffect, useState } from 'react'

type Health = { status: string; elasticsearch: string }

export default function HealthLine() {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'down', elasticsearch: 'unknown' }))
  }, [])

  return (
    <p className="health-line">
      API: {health?.status ?? '…'} · Elasticsearch: {health?.elasticsearch ?? '…'}
    </p>
  )
}
