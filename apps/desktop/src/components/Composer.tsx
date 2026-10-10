import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ArrowUp, FolderGit2, Mic, ShieldAlert, Square, X } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { disarmUnrestricted, getDraft, setDraft, useUnrestrictedArmed } from '../lib/prefs'
import { notYet } from '../lib/toast'
import { ModelPicker } from './ModelPicker'
import { PlusMenu } from './PlusMenu'
import { Tip } from './Tip'

export interface ComposerRepo {
  value: string
  placeholder: string
  onChange: (v: string) => void
}

interface ComposerProps {
  onSend: (text: string) => void
  /** 新会话里显示仓库签 */
  repo?: ComposerRepo
  /** 任务进行中：发送键变成停止键 */
  running?: boolean
  onStop?: () => void
  /** 可以不写任务就发送（演示模式） */
  allowEmpty?: boolean
  /** 草稿按会话保存 */
  draftKey?: string
}

const MAX_H = 240

/**
 * Claude 式输入框：上面是自动增高的文本区；下面一行左边 +、仓库签，右边模型选择与发送 / 停止。
 * Enter 发送、Shift+Enter 换行、Esc 停止；草稿按会话保存。
 */
export function Composer({ onSend, repo, running, onStop, allowEmpty, draftKey = 'default' }: ComposerProps) {
  const [value, setValue] = useState(() => getDraft(draftKey))
  const [menu, setMenu] = useState<'plus' | 'model' | 'effort' | null>(null)
  const armed = useUnrestrictedArmed()
  const [editingRepo, setEditingRepo] = useState(false)
  const ta = useRef<HTMLTextAreaElement>(null)

  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(MAX_H, el.scrollHeight)}px`
    el.style.overflowY = el.scrollHeight > MAX_H ? 'auto' : 'hidden'
  }, [value])

  useEffect(() => {
    const t = window.setTimeout(() => setDraft(draftKey, value), 200)
    return () => window.clearTimeout(t)
  }, [value, draftKey])

  useEffect(() => {
    const focus = () => ta.current?.focus()
    const model = () => setMenu('model')
    const effort = () => setMenu('effort')
    window.addEventListener('tw:focus-composer', focus)
    window.addEventListener('tw:model-menu', model)
    window.addEventListener('tw:effort-menu', effort)
    return () => {
      window.removeEventListener('tw:focus-composer', focus)
      window.removeEventListener('tw:model-menu', model)
      window.removeEventListener('tw:effort-menu', effort)
    }
  }, [])

  const canSend = !running && (!!value.trim() || !!allowEmpty)
  const submit = () => {
    if (!canSend) return
    onSend(value.trim())
    setValue('')
    setDraft(draftKey, '')
  }

  return (
    <div className="px-8 pb-6 pt-2">
      <div
        data-testid="composer"
        className="paper-card mx-auto max-w-[760px] rounded-[22px] px-3 pb-2.5 pt-3 transition-shadow duration-500 focus-within:shadow-[0_6px_28px_-10px_rgb(122_101_80/0.35)]"
      >
        <textarea
          ref={ta}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            } else if (e.key === 'Escape' && running) {
              e.preventDefault()
              onStop?.()
            }
          }}
          rows={1}
          placeholder="写下任务…"
          aria-label="输入"
          className="block max-h-[240px] min-h-[44px] w-full resize-none bg-transparent px-1.5 py-1 font-serif text-[15px] leading-relaxed text-ink outline-none placeholder:text-sepia-muted/80"
        />
        <div className="mt-1.5 flex items-center gap-2">
          <PlusMenu open={menu === 'plus'} onOpenChange={(o) => setMenu(o ? 'plus' : null)} />
          {repo &&
            (editingRepo ? (
              <input
                autoFocus
                data-testid="repo-input"
                value={repo.value}
                onChange={(e) => repo.onChange(e.target.value)}
                onBlur={() => setEditingRepo(false)}
                onKeyDown={(e) => e.key === 'Enter' && setEditingRepo(false)}
                placeholder={repo.placeholder}
                spellCheck={false}
                className="chip w-full max-w-[300px] bg-transparent font-mono text-[11.5px] outline-none placeholder:text-sepia-muted/70"
              />
            ) : (
              <Tip label="仓库路径" side="top-start">
                <button
                  type="button"
                  data-testid="repo-chip"
                  onClick={() => setEditingRepo(true)}
                  className="chip max-w-[300px] truncate transition-colors duration-300 hover:text-amber"
                >
                  <FolderGit2 size={11} strokeWidth={1.7} />
                  <span className="truncate font-mono text-[11.5px]">{repo.value || repo.placeholder}</span>
                </button>
              </Tip>
            ))}
          {armed && (
            <span data-testid="unrestricted-chip" className="chip fade-in border-rose-ink/40 bg-rose-ink/10 text-rose-ink">
              <ShieldAlert size={11} strokeWidth={1.8} />
              勇士模式
              <button type="button" aria-label="取消勇士模式" onClick={disarmUnrestricted} className="-mr-1 rounded-full p-0.5 hover:bg-rose-ink/15">
                <X size={10} strokeWidth={2} />
              </button>
            </span>
          )}
          <div className="ml-auto flex items-center gap-1">
            <ModelPicker
              open={menu === 'model' || menu === 'effort'}
              effort={menu === 'effort'}
              onOpenChange={(o) => setMenu(o ? 'model' : null)}
            />
            <SendSlot running={!!running} canSend={canSend} onSend={submit} onStop={onStop} />
          </div>
        </div>
      </div>
    </div>
  )
}

/** 发送位：有字 → 发送；空 → 语音；进行中 → 停止。三者之间做一次轻弹切换 */
function SendSlot({
  running,
  canSend,
  onSend,
  onStop,
}: {
  running: boolean
  canSend: boolean
  onSend: () => void
  onStop?: () => void
}) {
  const kind = running ? 'stop' : canSend ? 'send' : 'mic'
  const base =
    'inline-flex h-8 w-8 items-center justify-center rounded-[10px] transition-colors duration-300'
  return (
    <div className="relative h-8 w-8">
      <AnimatePresence initial={false} mode="popLayout">
        <motion.div
          key={kind}
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.7 }}
          transition={{ type: 'spring', stiffness: 600, damping: 30 }}
          className="absolute inset-0"
        >
          {kind === 'stop' ? (
            <Tip label="停止 · Esc" side="top-end">
              <button type="button" onClick={onStop} aria-label="停止" data-testid="stop" className={`${base} bg-ink text-parchment hover:bg-espresso`}>
                <Square size={11} strokeWidth={2} fill="currentColor" />
              </button>
            </Tip>
          ) : kind === 'send' ? (
            <Tip label="发送 · Enter" side="top-end">
              <button type="button" onClick={onSend} aria-label="发送" data-testid="send" className={`${base} bg-amber text-cream hover:bg-[#b07433]`}>
                <ArrowUp size={16} strokeWidth={2} />
              </button>
            </Tip>
          ) : (
            <Tip label="语音输入" side="top-end">
              <button type="button" onClick={() => notYet('语音输入')} aria-label="语音输入" data-testid="mic" className={`${base} text-sepia hover:bg-panel-raised hover:text-amber`}>
                <Mic size={15} strokeWidth={1.6} />
              </button>
            </Tip>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
