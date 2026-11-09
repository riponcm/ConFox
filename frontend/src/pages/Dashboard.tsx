import HealthLine from '../components/HealthLine.tsx'
import PagePlaceholder from '../components/PagePlaceholder.tsx'

export default function Dashboard() {
  return (
    <PagePlaceholder
      title="Dashboard"
      description="See the conference at a glance: sessions over the day, what fills up next, and the tracks."
      pr={5}
    >
      <HealthLine />
    </PagePlaceholder>
  )
}
