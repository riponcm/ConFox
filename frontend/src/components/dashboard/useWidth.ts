import { useCallback, useEffect, useState } from 'react'

/**
 * The element's content width, kept current with a ResizeObserver. Returns a callback ref, so the observer
 * attaches whenever the element mounts, even if it first appears after an empty state.
 */
export function useWidth<T extends HTMLElement>() {
  const [node, setNode] = useState<T | null>(null)
  const [width, setWidth] = useState(0)
  const ref = useCallback((el: T | null) => setNode(el), [])
  useEffect(() => {
    if (!node) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    ro.observe(node)
    return () => ro.disconnect()
  }, [node])
  return [ref, width] as const
}
