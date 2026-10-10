import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, FileText, ImageIcon, Loader2, Paperclip, X } from 'lucide-react'
import clsx from 'clsx'
import { formatSize, type Attachment } from '../lib/attachments'
import { Dialog } from './Dialog'
import { Tip } from './Tip'

/** 输入框上方的附件签：缩略图 / 文件名 / 大小，× 移除，点开预览；进出用弹簧 */
export function AttachmentChips({ items, onRemove }: { items: Attachment[]; onRemove?: (id: string) => void }) {
  const [open, setOpen] = useState<Attachment | null>(null)
  const hasImage = items.some((a) => a.kind === 'image')
  return (
    <>
      <div data-testid="attachments" className="flex flex-wrap gap-2 px-1 pb-2">
        <AnimatePresence initial={false}>
          {items.map((a) => (
            <motion.div
              key={a.id}
              layout
              initial={{ opacity: 0, scale: 0.9, y: 4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, pointerEvents: 'none', scale: 0.9, transition: { duration: 0.12 } }}
              transition={{ type: 'spring', stiffness: 500, damping: 34 }}
              className="group relative"
            >
              <button
                type="button"
                data-testid="attachment-chip"
                data-status={a.status}
                onClick={() => setOpen(a)}
                className={clsx(
                  'flex h-[52px] max-w-[220px] items-center gap-2.5 rounded-xl border bg-cream/70 py-1.5 pl-1.5 pr-3 text-left transition-colors duration-300 hover:border-border',
                  a.status === 'error' ? 'border-rose-ink/40' : 'border-border-soft',
                )}
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-panel-raised text-sepia">
                  {a.kind === 'image' && a.preview ? (
                    <img src={a.preview} alt="" className="h-full w-full object-cover" />
                  ) : a.kind === 'image' ? (
                    <ImageIcon size={16} strokeWidth={1.6} />
                  ) : a.kind === 'text' ? (
                    <FileText size={16} strokeWidth={1.6} />
                  ) : (
                    <Paperclip size={16} strokeWidth={1.6} />
                  )}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[12.5px] text-ink">{a.name}</span>
                  <span className={clsx('flex items-center gap-1 text-[11px]', a.status === 'error' ? 'text-rose-ink' : 'text-sepia-muted')}>
                    {a.status === 'saving' && <Loader2 size={10} className="animate-spin" />}
                    {a.status === 'error' && <AlertCircle size={10} />}
                    {a.status === 'error' ? a.error : formatSize(a.size)}
                  </span>
                </span>
              </button>
              {onRemove && (
                <Tip label="移除">
                  <button
                    type="button"
                    aria-label={`移除 ${a.name}`}
                    data-testid="attachment-remove"
                    onClick={() => onRemove(a.id)}
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-parchment text-sepia shadow-sm transition-colors hover:text-rose-ink"
                  >
                    <X size={10} strokeWidth={2.2} />
                  </button>
                </Tip>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {hasImage && onRemove && (
        <p data-testid="image-note" className="px-2 pb-2 text-[11.5px] text-sepia-muted">
          当前模型只读文字：图片会作为文件附上，但看不到内容。
        </p>
      )}
      <Dialog open={!!open} onClose={() => setOpen(null)} title={open?.name} width={640} testId="attachment-preview">
        {open && (
          <div className="max-h-[60vh] overflow-auto rounded-xl border border-border-soft bg-cream/60">
            {open.kind === 'image' && open.preview ? (
              <img src={open.preview} alt={open.name} className="mx-auto max-h-[58vh] object-contain" />
            ) : open.kind === 'text' && open.preview ? (
              <pre className="selectable whitespace-pre-wrap p-3 font-mono text-[12px] leading-relaxed text-ink-soft">{open.preview}</pre>
            ) : (
              <p className="p-4 text-[13px] text-sepia">{formatSize(open.size)} · 无法预览</p>
            )}
          </div>
        )}
      </Dialog>
    </>
  )
}
