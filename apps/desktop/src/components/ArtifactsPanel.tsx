import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Code2, Download, FileDiff, FileText, X } from 'lucide-react'
import clsx from 'clsx'
import { diffLineKind, diffStats, fileNameOf, type Artifact } from '../lib/artifacts'
import { MAX_ARTIFACT_W, MIN_ARTIFACT_W, getPrefs, setPrefs } from '../lib/prefs'
import { saveText } from '../lib/download'
import { CopyButton, Markdown } from './Markdown'
import { Tip } from './Tip'
import { t } from '../lib/i18n'

export function ArtifactIcon({ kind, size = 14 }: { kind: Artifact['kind']; size?: number }) {
  const I = kind === 'diff' ? FileDiff : kind === 'markdown' ? FileText : Code2
  return <I size={size} strokeWidth={1.6} />
}

/**
 * 作品侧栏（照 Claude Artifacts）：右侧滑出，可拖动左边缘调宽；版本切换、复制、下载、关闭。
 * 代码等宽带行号，补丁按增删着色，Markdown 排版渲染。
 */
export function ArtifactsPanel({
  artifact,
  width,
  version,
  onVersion,
  onClose,
}: {
  artifact: Artifact
  width: number
  version: number
  onVersion: (i: number) => void
  onClose: () => void
}) {
  const [w, setW] = useState(width)
  const [drag, setDrag] = useState(false)
  const start = useRef<{ x: number; w: number } | null>(null)
  const v = Math.min(version, artifact.versions.length - 1)
  const content = artifact.versions[v]?.content ?? ''
  const total = artifact.versions.length

  useEffect(() => {
    if (!drag) return
    const move = (e: PointerEvent) => {
      if (!start.current) return
      const max = Math.min(MAX_ARTIFACT_W, window.innerWidth - 520)
      setW(Math.round(Math.min(max, Math.max(MIN_ARTIFACT_W, start.current.w + start.current.x - e.clientX))))
    }
    const up = () => {
      setDrag(false)
      start.current = null
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [drag])
  useEffect(() => {
    if (!drag && w !== getPrefs().artifactWidth) setPrefs({ artifactWidth: w })
  }, [drag, w])

  const stats = artifact.kind === 'diff' ? diffStats(content) : null
  return (
    <motion.aside
      data-testid="artifact-panel"
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: w, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={drag ? { duration: 0 } : { type: 'spring', stiffness: 360, damping: 38, mass: 0.9 }}
      className={clsx('relative flex h-full shrink-0 flex-col overflow-hidden border-l border-border-soft bg-panel/70', drag && 'select-none')}
    >
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={t('调整宽度')}
        aria-valuenow={w}
        aria-valuemin={MIN_ARTIFACT_W}
        aria-valuemax={MAX_ARTIFACT_W}
        tabIndex={0}
        data-testid="artifact-resize"
        onPointerDown={(e) => {
          start.current = { x: e.clientX, w }
          setDrag(true)
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
            e.preventDefault()
            const next = Math.min(MAX_ARTIFACT_W, Math.max(MIN_ARTIFACT_W, w + (e.key === 'ArrowLeft' ? 32 : -32)))
            setW(next)
          }
        }}
        className="group absolute inset-y-0 left-0 z-10 w-1.5 cursor-col-resize outline-none"
      >
        <span className={clsx('absolute inset-y-0 left-0 w-px transition-colors duration-300 group-hover:bg-amber/60 group-focus-visible:bg-amber', drag && 'bg-amber')} />
      </div>
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border-soft px-4" style={{ minWidth: MIN_ARTIFACT_W }}>
        <span className="text-sepia">
          <ArtifactIcon kind={artifact.kind} />
        </span>
        <h3 data-testid="artifact-title" className="min-w-0 truncate font-serif text-[15px] text-ink">
          {artifact.title}
        </h3>
        {stats && (
          <span className="shrink-0 font-mono text-[11px]">
            <span className="text-sage">+{stats.add}</span> <span className="text-rose-ink">−{stats.del}</span>
          </span>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          {total > 1 && (
            <div data-testid="artifact-versions" className="mr-1 flex items-center gap-0.5 text-[11.5px] text-sepia-muted">
              <button type="button" aria-label={t('上一版')} disabled={v === 0} onClick={() => onVersion(v - 1)} className="rounded p-1 hover:bg-panel-raised disabled:opacity-30">
                <ChevronLeft size={13} />
              </button>
              <span className="tabular-nums">{t('版本 {0}/{1}', v + 1, total)}</span>
              <button type="button" aria-label={t('下一版')} disabled={v === total - 1} onClick={() => onVersion(v + 1)} className="rounded p-1 hover:bg-panel-raised disabled:opacity-30">
                <ChevronRight size={13} />
              </button>
            </div>
          )}
          <Tip label={t('复制')} side="bottom">
            <span>
              <CopyButton text={content} label={t('复制')} />
            </span>
          </Tip>
          <Tip label={t('下载')} side="bottom">
            <button
              type="button"
              aria-label={t('下载')}
              data-testid="artifact-download"
              onClick={() => void saveText(fileNameOf(artifact), content)}
              className="inline-flex h-6 items-center rounded-md px-1.5 text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-amber-ink"
            >
              <Download size={13} strokeWidth={1.6} />
            </button>
          </Tip>
          <Tip label={t('关闭 · Esc')} side="bottom">
            <button
              type="button"
              aria-label={t('关闭作品')}
              data-testid="artifact-close"
              onClick={onClose}
              className="inline-flex h-6 items-center rounded-md px-1.5 text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-ink"
            >
              <X size={14} strokeWidth={1.7} />
            </button>
          </Tip>
        </div>
      </header>
      <div data-testid="artifact-body" className="min-h-0 flex-1 overflow-auto scroll-soft" style={{ minWidth: MIN_ARTIFACT_W }}>
        {artifact.kind === 'markdown' ? (
          <div className="chat-zoom px-6 py-5">
            <Markdown text={content} />
          </div>
        ) : (
          <pre className="selectable min-w-max py-3 font-mono text-[12.5px] leading-[1.65] text-ink">
            {content.split('\n').map((line, i) => {
              const k = artifact.kind === 'diff' ? diffLineKind(line) : 'ctx'
              return (
                <div
                  key={i}
                  className={clsx(
                    'flex pr-4',
                    k === 'add' && 'bg-sage/12',
                    k === 'del' && 'bg-rose-ink/10',
                    k === 'hunk' && 'text-teal',
                    k === 'meta' && 'text-sepia-muted',
                  )}
                >
                  <span className="w-11 shrink-0 select-none pr-3 text-right text-sepia-muted/60">{i + 1}</span>
                  <span className="whitespace-pre">{line || ' '}</span>
                </div>
              )
            })}
          </pre>
        )}
      </div>
    </motion.aside>
  )
}

/** 对话里的作品卡（Claude 式）：点开右侧作品栏 */
export function ArtifactCards({ items, activeId, onOpen }: { items: Artifact[]; activeId: string | null; onOpen: (id: string) => void }) {
  if (!items.length) return null
  return (
    <div data-testid="artifact-cards" className="grid gap-2 sm:grid-cols-2">
      {items.map((a) => {
        const last = a.versions[a.versions.length - 1]?.content ?? ''
        const lines = last.split('\n').length
        return (
          <button
            key={a.id}
            type="button"
            data-testid="artifact-card"
            onClick={() => onOpen(a.id)}
            className={clsx(
              'paper-card fade-in flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-[border-color,transform] duration-300 hover:-translate-y-px hover:border-border',
              activeId === a.id && 'border-amber/50',
            )}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-panel-raised text-sepia">
              <ArtifactIcon kind={a.kind} size={16} />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[13px] text-ink">{a.title}</span>
              <span className="block text-[11px] text-sepia-muted">{t('{0} · {1} 行{2}', a.kind === 'diff' ? t('补丁') : a.kind === 'markdown' ? t('文档') : t('代码'), lines, a.versions.length > 1 ? t(' · {0} 个版本', a.versions.length) : '')}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
