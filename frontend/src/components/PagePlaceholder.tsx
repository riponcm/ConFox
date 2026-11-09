import type { ReactNode } from 'react'

type Props = { title: string; description: string; pr: number; children?: ReactNode }

export default function PagePlaceholder({ title, description, pr, children }: Props) {
  return (
    <section className="page" aria-labelledby="page-title">
      <h1 id="page-title">{title}</h1>
      <p className="page-lead">{description}</p>
      <p className="page-note">Arrives in PR {pr}</p>
      {children}
    </section>
  )
}
