import { useState } from 'react'
import { ArrowUp, Paperclip } from 'lucide-react'
import { Tip } from './Tip'

export function Composer({ onSend }: { onSend: (text: string) => void }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const t = value.trim()
    if (!t) return
    onSend(t)
    setValue('')
  }

  return (
    <div className="px-8 pb-6 pt-2">
      <div className="paper-card mx-auto flex max-w-[760px] items-end gap-2 rounded-2xl p-2.5 pl-3">
        <Tip label="附件">
          <button
            type="button"
            aria-label="附件"
            className="mb-1 inline-flex h-8 w-8 items-center justify-center rounded-full text-sepia-muted transition-colors duration-300 hover:text-amber"
          >
            <Paperclip size={15} strokeWidth={1.6} />
          </button>
        </Tip>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          rows={1}
          placeholder="写下任务…"
          className="max-h-36 min-h-[40px] flex-1 resize-none bg-transparent py-2.5 font-serif text-[14.5px] leading-relaxed text-ink outline-none placeholder:text-sepia-muted/80"
        />
        <Tip label="发送 · Enter" side="top-end">
          <button
            type="button"
            onClick={submit}
            disabled={!value.trim()}
            aria-label="发送"
            className="mb-1 inline-flex h-9 w-9 items-center justify-center rounded-full bg-ink text-parchment transition-all duration-300 enabled:hover:bg-espresso disabled:opacity-25"
          >
            <ArrowUp size={16} strokeWidth={1.8} />
          </button>
        </Tip>
      </div>
    </div>
  )
}
