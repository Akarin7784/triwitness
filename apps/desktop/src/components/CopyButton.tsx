import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { t } from '../lib/i18n'

export function CopyButton({ text, label = t('复制'), className }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      aria-label={label}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setDone(true)
          window.setTimeout(() => setDone(false), 1400)
        })
      }}
      className={
        className ??
        'inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[13px] text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-amber-ink'
      }
    >
      {done ? <Check size={12} strokeWidth={1.8} /> : <Copy size={12} strokeWidth={1.6} />}
      {done ? t('已复制') : null}
    </button>
  )
}
