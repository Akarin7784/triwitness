import { Pencil, RotateCcw, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { Turn } from '../data/turns'
import { notYet } from '../lib/toast'
import { CopyButton, Markdown } from './Markdown'
import { StreamingText } from './StreamingText'
import { ThinkingBlock } from './ThinkingBlock'
import { ToolRow } from './ToolRow'
import { Tip } from './Tip'

const ACT =
  'inline-flex h-7 w-7 items-center justify-center rounded-md text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-ink-soft'

/** 一轮对话：用户消息（气泡）+ 助手（无气泡）：思考块 · 正文 · 工具行交错，收尾摘要与操作条 */
export function AssistantTurn({ turn }: { turn: Turn }) {
  const last = turn.blocks[turn.blocks.length - 1]
  const answer = [
    ...turn.blocks.flatMap((b) => (b.type === 'text' ? [b.text] : [])),
    ...(turn.final ? [turn.final.text] : []),
  ].join('\n\n')
  return (
    <div className="space-y-3">
      {turn.user && (
        <article className="group ml-auto max-w-[620px] fade-in">
          <div className="rounded-2xl bg-ink px-4 py-3 text-parchment shadow-md">
            <p className="selectable whitespace-pre-wrap text-[14px] leading-[1.8]">{turn.user.text}</p>
          </div>
          <div className="mt-1 flex h-7 items-center justify-end gap-0.5 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
            <span className="mr-1 text-[10px] tabular-nums text-sepia-muted">{turn.user.time}</span>
            <Tip label="编辑">
              <button type="button" aria-label="编辑" className={ACT} onClick={() => notYet('编辑后重发')}>
                <Pencil size={13} strokeWidth={1.6} />
              </button>
            </Tip>
            <Tip label="复制">
              <CopyButton text={turn.user.text} className={ACT} />
            </Tip>
          </div>
        </article>
      )}

      {turn.blocks.length > 0 && (
        <div data-testid="assistant-turn" className="max-w-[720px]">
          {turn.blocks.map((b) =>
            b.type === 'thinking' ? (
              <ThinkingBlock key={b.id} block={b} />
            ) : b.type === 'tool' ? (
              <ToolRow key={b.id} block={b} />
            ) : (
              <div key={b.id} className="my-2">
                <StreamingText text={b.text} streaming={!b.done && b === last} />
              </div>
            ),
          )}
          {turn.final && (
            <div className="fade-in mt-3 border-t border-border-soft pt-3">
              <Markdown text={turn.final.text} />
            </div>
          )}
          {!turn.streaming && turn.final && (
            <div data-testid="message-actions" className="fade-in mt-1.5 flex items-center gap-0.5">
              <Tip label="复制">
                <CopyButton text={answer} className={ACT} />
              </Tip>
              <Tip label="重试">
                <button type="button" aria-label="重试" className={ACT} onClick={() => notYet('重试')}>
                  <RotateCcw size={13} strokeWidth={1.6} />
                </button>
              </Tip>
              <Tip label="有帮助">
                <button type="button" aria-label="有帮助" className={ACT} onClick={() => notYet('反馈')}>
                  <ThumbsUp size={13} strokeWidth={1.6} />
                </button>
              </Tip>
              <Tip label="没帮助">
                <button type="button" aria-label="没帮助" className={ACT} onClick={() => notYet('反馈')}>
                  <ThumbsDown size={13} strokeWidth={1.6} />
                </button>
              </Tip>
              <span className="ml-2 text-[10.5px] text-sepia-muted">{turn.final.meta}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

