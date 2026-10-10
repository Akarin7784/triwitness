import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState } from 'react'
import { ArrowUp, FolderGit2, FolderKanban, Mic, Palette, ShieldAlert, Square, X } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { PRESET_STYLES, disarmUnrestricted, getDraft, setDraft, setPrefs, usePrefs, useUnrestrictedArmed } from '../lib/prefs'
import { ATTACH_EVENT, MAX_FILES, newAttachment, saveFile, type Attachment } from '../lib/attachments'
import { notYet, toast } from '../lib/toast'
import { AttachmentChips } from './Attachments'
import { ModelPicker } from './ModelPicker'
import { PlusMenu } from './PlusMenu'
import { StyleDialog } from './StyleDialog'
import { Tip } from './Tip'
import { t as tr } from '../lib/i18n'

export interface ComposerRepo {
  value: string
  placeholder: string
  onChange: (v: string) => void
}

interface ComposerProps {
  onSend: (text: string, attachments: Attachment[]) => void
  /** 会话所属项目（显示项目签） */
  project?: string
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
export function Composer({ onSend, repo, running, onStop, allowEmpty, draftKey = 'default', project }: ComposerProps) {
  const [value, setValue] = useState(() => getDraft(draftKey))
  const [menu, setMenu] = useState<'plus' | 'model' | 'effort' | null>(null)
  const armed = useUnrestrictedArmed()
  const prefs = usePrefs()
  const [editingRepo, setEditingRepo] = useState(false)
  const [atts, setAtts] = useState<Attachment[]>([])
  const [styles, setStyles] = useState(false)
  const ta = useRef<HTMLTextAreaElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const addFiles = (files: File[]) => {
    setAtts((cur) => {
      const room = MAX_FILES - cur.length
      if (files.length > room) toast(tr('最多 {0} 个附件', MAX_FILES))
      const fresh = files.slice(0, Math.max(0, room)).map((f) => ({ f, a: newAttachment(f) }))
      for (const { f, a } of fresh) {
        void saveFile(f, a).then((done) => setAtts((list) => list.map((x) => (x.id === a.id ? done : x))))
      }
      return [...cur, ...fresh.map((x) => x.a)]
    })
    ta.current?.focus()
  }
  const onFiles = useEffectEvent((files: File[]) => addFiles(files))
  const removeAtt = (id: string) =>
    setAtts((list) => {
      const gone = list.find((a) => a.id === id)
      if (gone?.preview?.startsWith('blob:')) URL.revokeObjectURL(gone.preview)
      return list.filter((a) => a.id !== id)
    })

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
    const pick = () => fileInput.current?.click()
    const files = (e: Event) => onFiles((e as CustomEvent<File[]>).detail ?? [])
    window.addEventListener('tw:focus-composer', focus)
    window.addEventListener('tw:model-menu', model)
    window.addEventListener('tw:effort-menu', effort)
    window.addEventListener('tw:attach-pick', pick)
    window.addEventListener(ATTACH_EVENT, files)
    return () => {
      window.removeEventListener('tw:focus-composer', focus)
      window.removeEventListener('tw:model-menu', model)
      window.removeEventListener('tw:effort-menu', effort)
      window.removeEventListener('tw:attach-pick', pick)
      window.removeEventListener(ATTACH_EVENT, files)
    }
  }, [])

  const saving = atts.some((a) => a.status === 'saving')
  const canSend = !running && !saving && (!!value.trim() || !!allowEmpty)
  const submit = () => {
    if (!canSend) return
    onSend(value.trim(), atts.filter((a) => a.status === 'ready'))
    setValue('')
    setDraft(draftKey, '')
    setAtts([])
  }
  const styleName =
    prefs.style === 'standard'
      ? null
      : (PRESET_STYLES.find((p) => p.id === prefs.style)?.name ?? prefs.customStyles.find((c) => c.id === prefs.style)?.name)

  return (
    <div className="px-8 pb-6 pt-2">
      <div
        data-testid="composer"
        className="paper-card mx-auto max-w-[760px] rounded-[22px] px-3 pb-2.5 pt-3 transition-shadow duration-500 focus-within:shadow-[0_6px_28px_-10px_rgb(122_101_80/0.35)]"
      >
        {atts.length > 0 && <AttachmentChips items={atts} onRemove={removeAtt} />}
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          data-testid="file-input"
          onChange={(e) => {
            addFiles([...(e.target.files ?? [])])
            e.target.value = ''
          }}
        />
        <textarea
          ref={ta}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onPaste={(e) => {
            const files = [...e.clipboardData.files]
            if (files.length) {
              e.preventDefault()
              addFiles(files)
            }
          }}
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
          placeholder={tr('写下任务…')}
          aria-label={tr('输入')}
          className="block max-h-[240px] min-h-[44px] w-full resize-none bg-transparent px-1.5 py-1 font-serif text-[15px] leading-relaxed text-ink outline-none placeholder:text-sepia-muted/80"
        />
        <div className="mt-1.5 flex items-center gap-2">
          <PlusMenu
            open={menu === 'plus'}
            onOpenChange={(o) => setMenu(o ? 'plus' : null)}
            onAttach={() => fileInput.current?.click()}
            onEditStyles={() => setStyles(true)}
          />
          {project && (
            <span data-testid="project-chip" className="chip max-w-[180px] truncate">
              <FolderKanban size={11} strokeWidth={1.7} />
              <span className="truncate">{project}</span>
            </span>
          )}
          {styleName && (
            <span data-testid="style-chip" className="chip fade-in">
              <Palette size={11} strokeWidth={1.7} />
              {styleName}
              <button type="button" aria-label={tr('恢复标准风格')} onClick={() => setPrefs({ style: 'standard' })} className="-mr-1 rounded-full p-0.5 hover:bg-panel-raised">
                <X size={10} strokeWidth={2} />
              </button>
            </span>
          )}
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
              <Tip label={tr('仓库路径')} side="top-start">
                <button
                  type="button"
                  data-testid="repo-chip"
                  onClick={() => setEditingRepo(true)}
                  className="chip max-w-[300px] truncate transition-colors duration-300 hover:text-amber-ink"
                >
                  <FolderGit2 size={11} strokeWidth={1.7} />
                  <span className="truncate font-mono text-[11.5px]">{repo.value || repo.placeholder}</span>
                </button>
              </Tip>
            ))}
          {armed && (
            <span data-testid="unrestricted-chip" className="chip fade-in border-rose-ink/40 bg-rose-ink/10 text-rose-ink">
              <ShieldAlert size={11} strokeWidth={1.8} />
              {tr('勇士模式')}
              <button type="button" aria-label={tr('取消勇士模式')} onClick={disarmUnrestricted} className="-mr-1 rounded-full p-0.5 hover:bg-rose-ink/15">
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
      <StyleDialog open={styles} onClose={() => setStyles(false)} />
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
            <Tip label={tr('停止 · Esc')} side="top-end">
              <button type="button" onClick={onStop} aria-label={tr('停止')} data-testid="stop" className={`${base} bg-ink text-parchment hover:bg-espresso`}>
                <Square size={11} strokeWidth={2} fill="currentColor" />
              </button>
            </Tip>
          ) : kind === 'send' ? (
            <Tip label={tr('发送 · Enter')} side="top-end">
              <button type="button" onClick={onSend} aria-label={tr('发送')} data-testid="send" className={`${base} bg-amber text-cream hover:bg-[#b07433]`}>
                <ArrowUp size={16} strokeWidth={2} />
              </button>
            </Tip>
          ) : (
            <Tip label={tr('语音输入')} side="top-end">
              <button type="button" onClick={() => notYet(tr('语音输入'))} aria-label={tr('语音输入')} data-testid="mic" className={`${base} text-sepia hover:bg-panel-raised hover:text-amber-ink`}>
                <Mic size={15} strokeWidth={1.6} />
              </button>
            </Tip>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
