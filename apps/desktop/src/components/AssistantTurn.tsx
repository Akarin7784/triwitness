import { memo, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Paperclip, Pencil, Play, RotateCcw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import type { Block, Turn } from '../data/turns'
import type { Rating } from '../lib/chats'
import { CopyButton, Markdown } from './Markdown'
import { StreamingText } from './StreamingText'
import { ThinkingBlock } from './ThinkingBlock'
import { ToolRow } from './ToolRow'
import { VirtualList } from './VirtualList'
import { FeedbackDialog } from './ChatDialogs'
import { Tip } from './Tip'
import { t as tr } from '../lib/i18n'

const ACT =
  'inline-flex h-7 w-7 items-center justify-center rounded-md text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-ink-soft disabled:pointer-events-none disabled:opacity-40'

/** 块数超过它算“长回合”：关掉 framer 的 layout 动画（每次重渲染都要量全部 layout 节点） */
const LONG_TURN = 40

const blockKey = (b: Block) => b.id
/** 没量过的块的估计高度：工具行 / 思考块一行，正文按字数粗估 */
const estimateBlock = (b: Block) => (b.type === 'tool' ? 36 : b.type === 'thinking' ? 40 : 40 + Math.ceil(b.text.length / 42) * 27)

/** 一个块；块对象不可变（reduceTurn 只换最后一个），memo 让流式时其余块不重渲染 */
const BlockView = memo(function BlockView({ block: b, streaming }: { block: Block; streaming: boolean }) {
  if (b.type === 'thinking') return <ThinkingBlock block={b} />
  if (b.type === 'tool') return <ToolRow block={b} />
  return (
    <div className="cv-auto my-2">
      <StreamingText text={b.text} streaming={streaming} />
    </div>
  )
})

export interface VersionInfo {
  index: number
  total: number
  /** 编辑产生的版本显示在用户消息下，重试产生的显示在回复操作条上（与 Claude 一致） */
  at: 'user' | 'assistant'
  onSelect: (index: number) => void
}

export interface TurnActions {
  /** 当前能否重试 / 编辑（核心可用且不在生成中） */
  enabled: boolean
  onRetry: () => void
  onEdit: (text: string) => void
  /** 停止 / 中断的任务：从最近进度继续（0.3.2）；不可继续时不传 */
  onContinue?: () => void
  versions?: VersionInfo
  feedback?: Rating
  onFeedback: (rating: Rating | null, note?: string) => void
}

/** 停止 / 中断的任务：从最近进度继续 */
function ContinueButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      data-testid="continue"
      title={tr('从上次停下的进度继续（已改的文件、已通过的复现会沿用）')}
      className="mr-1.5 inline-flex items-center gap-1 rounded-full border border-border-soft px-2.5 py-0.5 text-[13px] text-ink-soft hover:bg-border-soft"
      onClick={onClick}
    >
      <Play size={11} strokeWidth={1.8} />
      {tr('继续')}
    </button>
  )
}

/** 一轮对话：用户消息（气泡）+ 助手（无气泡）：思考块 · 正文 · 工具行交错，收尾摘要与操作条 */
export function AssistantTurn({ turn, actions, attachments }: { turn: Turn; actions?: TurnActions; attachments?: string[] }) {
  const [editing, setEditing] = useState(false)
  const [fb, setFb] = useState<Rating | null>(null)
  const last = turn.blocks[turn.blocks.length - 1]
  // 整条复制的文本只在回合结束后才需要；流式中不逐帧拼接全部正文
  const done = !turn.streaming && !!turn.final
  const answer = useMemo(
    () =>
      done
        ? [...turn.blocks.flatMap((b) => (b.type === 'text' ? [b.text] : [])), ...(turn.final ? [turn.final.text] : [])].join('\n\n')
        : '',
    [done, turn.blocks, turn.final],
  )
  const long = turn.blocks.length > LONG_TURN
  const v = actions?.versions
  return (
    <div className="space-y-3">
      {turn.user && (
        <motion.article
          layout={long ? false : 'position'}
          className="group ml-auto max-w-[620px] fade-in"
          data-testid="user-message"
        >
          <AnimatePresence mode="wait" initial={false}>
            {editing && actions ? (
              <EditBox
                key="edit"
                initial={turn.user.text}
                onCancel={() => setEditing(false)}
                onSend={(text) => {
                  setEditing(false)
                  actions.onEdit(text)
                }}
              />
            ) : (
              <motion.div
                key="bubble"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ pointerEvents: 'none', opacity: 0, scale: 0.98, transition: { duration: 0.1 } }}
                className="user-bubble rounded-xl px-4 py-3 text-[length:var(--read-fs,16px)] leading-[1.7]"
              >
                <p className="selectable whitespace-pre-wrap text-[length:var(--read-fs,16px)] leading-[1.7]">{turn.user.text}</p>
              </motion.div>
            )}
          </AnimatePresence>
          {attachments && attachments.length > 0 && (
            <div data-testid="sent-attachments" className="mt-1.5 flex flex-wrap justify-end gap-1.5">
              {attachments.map((n) => (
                <span key={n} className="chip max-w-[200px] truncate">
                  <Paperclip size={10} strokeWidth={1.7} />
                  <span className="truncate">{n}</span>
                </span>
              ))}
            </div>
          )}
          {!editing && (
            <div
              className={clsx(
                'mt-1 flex h-7 items-center justify-end gap-0.5 transition-opacity duration-300',
                v?.at === 'user' ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
              )}
            >
              <span className="mr-1 text-[13px] tabular-nums text-sepia-muted">{turn.user.time}</span>
              {v?.at === 'user' && <VersionNav v={v} />}
              <Tip label={tr('编辑')}>
                <button
                  type="button"
                  aria-label={tr('编辑')}
                  data-testid="edit-message"
                  className={ACT}
                  disabled={!actions?.enabled}
                  onClick={() => setEditing(true)}
                >
                  <Pencil size={13} strokeWidth={1.6} />
                </button>
              </Tip>
              <Tip label={tr('复制')}>
                <CopyButton text={turn.user.text} className={ACT} />
              </Tip>
            </div>
          )}
        </motion.article>
      )}

      {turn.blocks.length > 0 && (
        <div data-testid="assistant-turn" className="max-w-[68em]">
          <VirtualList
            items={turn.blocks}
            itemKey={blockKey}
            estimate={estimateBlock}
            render={(b) => <BlockView block={b} streaming={b.type === 'text' && !b.done && b === last} />}
          />
          {turn.final?.text && (
            <div className="fade-in mt-3 border-t border-border-soft pt-3">
              <Markdown text={turn.final.text} />
            </div>
          )}
          {!turn.streaming && !turn.final && actions?.onContinue && (
            <div className="fade-in mt-1.5">
              <ContinueButton onClick={actions.onContinue} />
            </div>
          )}
          {!turn.streaming && turn.final && (
            <div data-testid="message-actions" className="fade-in mt-1.5 flex items-center gap-0.5">
              {actions?.onContinue && <ContinueButton onClick={actions.onContinue} />}
              <Tip label={tr('复制')}>
                <CopyButton text={answer} className={ACT} />
              </Tip>
              <Tip label={tr('重试')}>
                <button type="button" aria-label={tr('重试')} data-testid="retry" className={ACT} disabled={!actions?.enabled} onClick={actions?.onRetry}>
                  <RotateCcw size={13} strokeWidth={1.6} />
                </button>
              </Tip>
              <Tip label={tr('有帮助')}>
                <button
                  type="button"
                  aria-label={tr('有帮助')}
                  aria-pressed={actions?.feedback === 'up'}
                  data-testid="thumb-up"
                  className={clsx(ACT, actions?.feedback === 'up' && 'text-sage')}
                  onClick={() => (actions?.feedback === 'up' ? actions.onFeedback(null) : setFb('up'))}
                >
                  <ThumbsUp size={13} strokeWidth={1.6} className={clsx(actions?.feedback === 'up' && 'fill-sage/25')} />
                </button>
              </Tip>
              <Tip label={tr('没帮助')}>
                <button
                  type="button"
                  aria-label={tr('没帮助')}
                  aria-pressed={actions?.feedback === 'down'}
                  data-testid="thumb-down"
                  className={clsx(ACT, actions?.feedback === 'down' && 'text-rose-ink')}
                  onClick={() => (actions?.feedback === 'down' ? actions.onFeedback(null) : setFb('down'))}
                >
                  <ThumbsDown size={13} strokeWidth={1.6} className={clsx(actions?.feedback === 'down' && 'fill-rose-ink/25')} />
                </button>
              </Tip>
              {v?.at === 'assistant' && <VersionNav v={v} />}
              <span className="ml-2 text-[13px] text-sepia-muted">{turn.final.meta}</span>
            </div>
          )}
          {(turn.streaming || !turn.final) && v?.at === 'assistant' && (
            <div className="mt-1.5 flex items-center">
              <VersionNav v={v} />
            </div>
          )}
        </div>
      )}
      <FeedbackDialog rating={fb} onClose={() => setFb(null)} onSubmit={(note) => fb && actions?.onFeedback(fb, note)} />
    </div>
  )
}

function VersionNav({ v }: { v: VersionInfo }) {
  return (
    <span data-testid="version-nav" className="mx-1 inline-flex items-center gap-0.5 text-[13px] tabular-nums text-sepia">
      <button type="button" aria-label={tr('上一版')} className={ACT} disabled={v.index <= 0} onClick={() => v.onSelect(v.index - 1)}>
        <ChevronLeft size={13} strokeWidth={1.7} />
      </button>
      <motion.span key={v.index} initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} className="min-w-[2.6em] text-center">
        {v.index + 1} / {v.total}
      </motion.span>
      <button type="button" aria-label={tr('下一版')} className={ACT} disabled={v.index >= v.total - 1} onClick={() => v.onSelect(v.index + 1)}>
        <ChevronRight size={13} strokeWidth={1.7} />
      </button>
    </span>
  )
}

function EditBox({ initial, onCancel, onSend }: { initial: string; onCancel: () => void; onSend: (t: string) => void }) {
  const [v, setV] = useState(initial)
  const ta = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(320, el.scrollHeight)}px`
  }, [v])
  useLayoutEffect(() => {
    const el = ta.current
    el?.focus()
    el?.setSelectionRange(el.value.length, el.value.length)
  }, [])
  const ok = !!v.trim() && v.trim() !== initial.trim()
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ pointerEvents: 'none', opacity: 0, scale: 0.98, transition: { duration: 0.1 } }}
      transition={{ type: 'spring', stiffness: 460, damping: 34 }}
      className="paper-card w-[min(620px,100%)] rounded-2xl p-3"
      data-testid="edit-box"
    >
      <textarea
        ref={ta}
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            if (ok) onSend(v.trim())
          } else if (e.key === 'Escape') {
            e.preventDefault()
            e.stopPropagation()
            onCancel()
          }
        }}
        aria-label={tr('编辑消息')}
        className="block w-full resize-none bg-transparent px-1 font-serif text-[14.5px] leading-relaxed text-ink outline-none"
      />
      <div className="mt-2 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-lg px-3 py-1 text-[13px] text-ink-soft hover:bg-panel-raised">
          {tr('取消')}
        </button>
        <button
          type="button"
          disabled={!ok}
          data-testid="edit-send"
          onClick={() => onSend(v.trim())}
          className="rounded-lg bg-ink px-3 py-1 text-[13px] text-parchment transition-colors duration-300 hover:bg-espresso disabled:opacity-40"
        >
          {tr('发送')}
        </button>
      </div>
    </motion.div>
  )
}
