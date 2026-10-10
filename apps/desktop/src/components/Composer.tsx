import { useState } from 'react'
import { ArrowUp, FolderGit2, Paperclip, Square } from 'lucide-react'
import { Tip } from './Tip'

export interface ComposerRepo {
  value: string
  placeholder: string
  onChange: (v: string) => void
}

interface ComposerProps {
  onSend: (text: string) => void
  /** 新会话里显示仓库路径签 */
  repo?: ComposerRepo
  /** 任务进行中：发送键变成停止键 */
  running?: boolean
  onStop?: () => void
  /** 可以不写任务就发送（演示模式） */
  allowEmpty?: boolean
}

export function Composer({ onSend, repo, running, onStop, allowEmpty }: ComposerProps) {
  const [value, setValue] = useState('')
  const [editingRepo, setEditingRepo] = useState(false)

  const canSend = !!value.trim() || !!allowEmpty
  const submit = () => {
    if (running || !canSend) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <div className="px-8 pb-6 pt-2">
      {repo && (
        <div className="mx-auto mb-2 flex max-w-[760px] px-1">
          {editingRepo ? (
            <input
              autoFocus
              data-testid="repo-input"
              value={repo.value}
              onChange={(e) => repo.onChange(e.target.value)}
              onBlur={() => setEditingRepo(false)}
              onKeyDown={(e) => e.key === 'Enter' && setEditingRepo(false)}
              placeholder={repo.placeholder}
              spellCheck={false}
              className="chip w-full max-w-[460px] bg-transparent font-mono text-[11.5px] outline-none placeholder:text-sepia-muted/70"
            />
          ) : (
            <Tip label="仓库路径" side="top-start">
              <button
                type="button"
                data-testid="repo-chip"
                onClick={() => setEditingRepo(true)}
                className="chip max-w-[460px] truncate transition-colors duration-300 hover:text-amber"
              >
                <FolderGit2 size={11} strokeWidth={1.7} />
                <span className="truncate font-mono text-[11.5px]">{repo.value || repo.placeholder}</span>
              </button>
            </Tip>
          )}
        </div>
      )}
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
        {running ? (
          <Tip label="停止" side="top-end">
            <button
              type="button"
              onClick={onStop}
              aria-label="停止"
              data-testid="stop"
              className="mb-1 inline-flex h-9 w-9 items-center justify-center rounded-full bg-ink text-parchment transition-all duration-300 hover:bg-espresso"
            >
              <Square size={12} strokeWidth={2} fill="currentColor" />
            </button>
          </Tip>
        ) : (
          <Tip label="发送 · Enter" side="top-end">
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              aria-label="发送"
              data-testid="send"
              className="mb-1 inline-flex h-9 w-9 items-center justify-center rounded-full bg-ink text-parchment transition-all duration-300 enabled:hover:bg-espresso disabled:opacity-25"
            >
              <ArrowUp size={16} strokeWidth={1.8} />
            </button>
          </Tip>
        )}
      </div>
    </div>
  )
}
