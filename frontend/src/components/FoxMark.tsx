// Geometric fox head: gradient face, light cheeks, dark eyes and nose.
export default function FoxMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="confox-fox-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: 'var(--fox-1)' }} />
          <stop offset="1" style={{ stopColor: 'var(--fox-2)' }} />
        </linearGradient>
      </defs>
      <path d="M5 4 L13 11 H19 L27 4 L28 16 L16 28 L4 16 Z" fill="url(#confox-fox-gradient)" />
      <path d="M4 16 L11 18.5 L16 28 Z M28 16 L21 18.5 L16 28 Z" style={{ fill: 'var(--fox-light)' }} />
      <g style={{ fill: 'var(--fox-ink)' }}>
        <circle cx="11.5" cy="15" r="1.4" />
        <circle cx="20.5" cy="15" r="1.4" />
        <path d="M14.4 25 H17.6 L16 27.4 Z" />
      </g>
    </svg>
  )
}
