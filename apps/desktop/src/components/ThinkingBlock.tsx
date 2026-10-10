import { useEffect, useRef, useState } from 'react'
import { ChevronRight, Sparkle } from 'lucide-react'
import clsx from 'clsx'
import { thinkingSeconds, type ThinkingBlock as Block } from '../data/turns'

/** 思考块：流式时展开显示推理（淡墨小字、自动跟底）；正文一开始就收成“思考了 N 秒”，可再展开 */
export function ThinkingBlock({ block }: { block: Block }) {
  const live = block.endMs === null
  const [open, setOpen] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)
  const expanded = live || open

  useEffect(() => {
    if (live && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [block.text, live])

  return (
    <div data-testid="thinking-block" className="my-1.5">
      <button
        type="button"
        onClick={() => !live && setOpen((o) => !o)}
        className={clsx(
          'group inline-flex items-center gap-1.5 rounded-md py-0.5 pr-1.5 text-[12.5px] transition-colors duration-300',
          live ? 'cursor-default text-amber' : 'text-sepia-muted hover:text-ink-soft',
        )}
      >
        <Sparkle size={12} strokeWidth={1.7} className={clsx(live && 'pulse-dot')} />
        <span className={clsx(live && 'think-shimmer')}>
          {live ? '思考中' : `思考了 ${thinkingSeconds(block)} 秒`}
        </span>
        {!live && (
          <ChevronRight size={12} strokeWidth={1.7} className={clsx('transition-transform duration-300', open && 'rotate-90')} />
        )}
      </button>
      <div className={clsx('grid transition-[grid-template-rows] duration-500 ease-out', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          <div
            ref={bodyRef}
            className={clsx(
              'selectable ml-[5px] mt-1 whitespace-pre-wrap border-l border-border pl-3.5 font-serif text-[12.5px] leading-[1.85] text-sepia',
              live && 'think-live max-h-32 overflow-y-auto scroll-soft',
            )}
          >
            {block.text}
          </div>
        </div>
      </div>
    </div>
  )
}
