import { useEffect, useState } from 'react'

/** 默认「减少动效」（电子书批次 1 决议）：只有 <html data-motion="standard"> 且系统未要求减少动画时才播放书写动画 */
function compute(): boolean {
  if (typeof window === 'undefined') return true
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return true
  return document.documentElement.dataset.motion !== 'standard'
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(compute)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(compute())
    mq.addEventListener('change', on)
    const mo = new MutationObserver(on)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-motion'] })
    return () => {
      mq.removeEventListener('change', on)
      mo.disconnect()
    }
  }, [])
  return reduced
}
