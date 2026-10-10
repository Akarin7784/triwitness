import { useRef, useState } from 'react'
import { ArrowDown, ChevronDown, ClipboardCopy, FileDown, FolderGit2, FolderPlus, Paperclip, Pencil, Printer, Share, ShieldAlert, Star, StarOff, Trash2 } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import type { ChatMessage } from '../types'
import { cacheHitRate, type RunView } from '../data/mapEvent'
import { MessageBubble } from './MessageBubble'
import { Composer, type ComposerRepo } from './Composer'
import { ApprovalCard } from './ApprovalCard'
import { ResultCard } from './ResultCard'
import type { PendingApproval } from '../bridge/liveTask'
import type { ApprovalScope, ResultMsg } from '../bridge/protocol'
import type { Turn } from '../data/turns'
import { AssistantTurn, type TurnActions } from './AssistantTurn'
import { MenuDivider, MenuItem, Popover } from './Popover'
import { dispatchFiles, type Attachment } from '../lib/attachments'
import type { Artifact } from '../lib/artifacts'
import { ArtifactCards } from './ArtifactsPanel'
import { ProjectPicker } from './ProjectPicker'
import { useStickToBottom } from '../hooks/useStickToBottom'
import { Tip } from './Tip'
import { PHASE_DOT } from './phase'
import { t } from '../lib/i18n'

interface ChatPanelProps {
  title: string
  run: RunView | null
  messages: ChatMessage[]
  onSend: (text: string, attachments: Attachment[]) => void
  /** 真实任务（UI-10） */
  approvals?: PendingApproval[]
  onApprove?: (requestId: string, decision: 'allow' | 'deny', scope: ApprovalScope) => Promise<void>
  result?: ResultMsg | null
  notice?: string | null
  repo?: ComposerRepo
  running?: boolean
  onStop?: () => void
  allowEmpty?: boolean
  /** 对话流（UI-20）：有就按 Claude 式一轮渲染，替代消息气泡 */
  turn?: Turn | null
  draftKey?: string
  /** 重试 / 编辑后重发 / 赞踩 / 版本（UI-21） */
  turnActions?: TurnActions
  /** 标题下拉（星标 / 重命名 / 加入项目 / 删除） */
  titleMenu?: TitleMenu
  /** 本任务以勇士模式运行（核心 mode_changed 事件，risk=high）：常驻红色横幅 */
  unrestricted?: boolean
  /** 分享 / 导出（只在本机） */
  share?: ShareActions
  /** 作品卡 */
  artifacts?: Artifact[]
  activeArtifact?: string | null
  onOpenArtifact?: (id: string) => void
  /** 会话所属项目名（输入框项目签） */
  project?: string
  /** 用户这轮带的附件名 */
  sentAttachments?: string[]
}

export interface TitleMenu {
  starred: boolean
  onStar: () => void
  onRename: () => void
  onDelete: () => void
  projects: { id: string; name: string }[]
  projectId: string | null
  onProject: (id: string | null) => void
}

export interface ShareActions {
  copyMarkdown: () => void
  exportMarkdown: () => void
  exportPdf: () => void
}

export function ChatPanel({
  title,
  run,
  messages,
  onSend,
  approvals = [],
  onApprove,
  result,
  notice,
  repo,
  running,
  onStop,
  allowEmpty,
  turn,
  draftKey,
  turnActions,
  titleMenu,
  unrestricted,
  share,
  artifacts = [],
  activeArtifact = null,
  onOpenArtifact,
  project,
  sentAttachments,
}: ChatPanelProps) {
  const { scrollRef, contentRef, atBottom, toBottom } = useStickToBottom<HTMLDivElement, HTMLDivElement>()
  const [dropping, setDropping] = useState(false)
  const depth = useRef(0)

  const pending = approvals.length > 0 && !result
  const hasFiles = (e: React.DragEvent) => [...e.dataTransfer.types].includes('Files')

  return (
    <section
      className="relative flex min-w-0 flex-1 flex-col"
      onDragEnter={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        depth.current++
        setDropping(true)
      }}
      onDragOver={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        e.dataTransfer.dropEffect = 'copy'
      }}
      onDragLeave={(e) => {
        if (!hasFiles(e)) return
        depth.current = Math.max(0, depth.current - 1)
        if (!depth.current) setDropping(false)
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        depth.current = 0
        setDropping(false)
        dispatchFiles([...e.dataTransfer.files])
      }}
    >
      <AnimatePresence>
        {dropping && (
          <motion.div
            data-testid="drop-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ pointerEvents: 'none', opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="pointer-events-none absolute inset-3 z-30 flex items-center justify-center rounded-3xl border-2 border-dashed border-amber/60 bg-parchment/80 backdrop-blur-[2px]"
          >
            <motion.div
              initial={{ scale: 0.94, y: 6 }}
              animate={{ scale: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 420, damping: 30 }}
              className="flex flex-col items-center gap-2 text-amber-ink"
            >
              <Paperclip size={22} strokeWidth={1.6} />
              <span className="font-serif text-[16px] text-ink">{t('把文件放到这里')}</span>
              <span className="text-[12px] text-sepia-muted">{t('文本会一起交给模型；图片只附文件')}</span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <header className="flex items-center justify-between gap-4 px-8 pb-3 pt-5">
        <TitleButton title={title} menu={titleMenu} />
        <div className="flex shrink-0 items-center gap-2">
        {run && (
          <>
            {run.repo && (
              <Tip label={t('仓库')} side="bottom">
                <span className="chip">
                  <FolderGit2 size={11} strokeWidth={1.7} />
                  {run.repo}
                </span>
              </Tip>
            )}
            <CostChip run={run} />
            {(run.label || pending) && (
              <span className="chip fade-in" key={pending ? t('待批') : run.label} data-testid="state-chip">
                <span
                  className={clsx(
                    'h-1.5 w-1.5 rounded-full transition-colors duration-700',
                    PHASE_DOT[pending ? 'waiting' : run.phase],
                  )}
                />
                {pending ? t('待批') : run.label}
              </span>
            )}
          </>
        )}
        {share && <ShareButton actions={share} />}
        </div>
      </header>
      <AnimatePresence initial={false}>
        {unrestricted && (
          <motion.div
            data-testid="unrestricted-banner"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            className="overflow-hidden"
          >
            <div className="mx-8 mb-2 flex items-center gap-2 rounded-xl border border-rose-ink/40 bg-rose-ink/10 px-3.5 py-2 text-[12.5px] text-rose-ink">
              <ShieldAlert size={14} strokeWidth={1.7} />
              <span className="font-medium">{t('无限制（勇士模式）')}</span>
              <span className="text-rose-ink/80">{t('本任务不确认、不拒绝')}</span>
              {running && onStop && (
                <button type="button" onClick={onStop} className="ml-auto rounded-md px-2 py-0.5 hover:bg-rose-ink/15">
                  {t('停止')}
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative min-h-0 flex-1">
      <div ref={scrollRef} data-testid="chat-scroll" className="h-full overflow-y-auto scroll-soft px-8 py-5">
      <div ref={contentRef} className="chat-zoom mx-auto max-w-[760px] space-y-3">
        {turn ? (
          <AssistantTurn key={draftKey} turn={turn} actions={turnActions} attachments={sentAttachments} />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
        {onOpenArtifact && <ArtifactCards items={artifacts} activeId={activeArtifact} onOpen={onOpenArtifact} />}
        {onApprove &&
          approvals.map((a) => (
            <ApprovalCard key={a.requestId} req={a} onDecide={(c) => onApprove(a.requestId, c.decision, c.scope)} />
          ))}
        {result && <ResultCard result={result} />}
        {notice && <p className="fade-in text-center text-[12px] text-sepia-muted">{notice}</p>}
      </div>
      </div>
      <AnimatePresence>
        {!atBottom && (
          <motion.button
            type="button"
            data-testid="jump-bottom"
            aria-label={t('回到底部')}
            onClick={() => toBottom()}
            initial={{ opacity: 0, y: 8, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ pointerEvents: 'none', opacity: 0, y: 6, scale: 0.92 }}
            transition={{ type: 'spring', stiffness: 500, damping: 32 }}
            className="paper-card absolute bottom-3 left-1/2 inline-flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full text-sepia hover:text-amber-ink"
          >
            <ArrowDown size={15} strokeWidth={1.7} />
          </motion.button>
        )}
      </AnimatePresence>
      </div>

      <Composer
        key={draftKey}
        draftKey={draftKey}
        onSend={onSend}
        repo={repo}
        running={running}
        onStop={onStop}
        allowEmpty={allowEmpty}
        project={project}
      />
    </section>
  )
}

function CostChip({ run }: { run: RunView }) {
  const hit = cacheHitRate(run)
  const ratio = run.budgetCny > 0 ? run.costCny / run.budgetCny : 0
  const tip = [
    hit !== null ? t('命中 {0}%', Math.round(hit * 100)) : null,
    t('上限 ¥{0}', run.budgetCny.toFixed(2)),
    run.peakCalls ? t('高峰 {0} 次', run.peakCalls) : null,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <Tip label={tip} side="bottom">
      <span
        data-testid="cost-chip"
        className={clsx(
          'chip tabular-nums transition-colors duration-700',
          ratio > 1 || run.phase === 'budget'
            ? 'border-rose-ink/40 text-rose-ink'
            : ratio > 0.8 || run.peakCalls > 0
              ? 'border-amber/50 text-amber-ink'
              : '',
        )}
      >
        ¥{run.costCny.toFixed(3)}
        <span className="relative h-1 w-8 overflow-hidden rounded-full bg-border-soft">
          <span
            className={clsx(
              'absolute inset-y-0 left-0 rounded-full transition-[width] duration-700',
              ratio > 1 ? 'bg-rose-ink/70' : 'bg-amber/70',
            )}
            style={{ width: `${Math.min(100, ratio * 100)}%` }}
          />
        </span>
      </span>
    </Tip>
  )
}

function TitleButton({ title, menu }: { title: string; menu?: TitleMenu }) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState<'main' | 'project'>('main')
  if (!menu) return <h2 className="min-w-0 truncate font-serif text-[20px] font-medium tracking-wide text-ink">{title}</h2>
  const close = () => {
    setOpen(false)
    window.setTimeout(() => setPage('main'), 200)
  }
  return (
    <div className="relative min-w-0">
      <button
        type="button"
        data-testid="title-menu"
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          '-ml-2 flex min-w-0 items-center gap-1.5 rounded-lg px-2 py-0.5 transition-colors duration-300 hover:bg-panel-raised',
          open && 'bg-panel-raised',
        )}
      >
        {menu.starred && <Star size={14} strokeWidth={1.6} className="shrink-0 fill-amber/70 text-amber-ink" />}
        <h2 className="min-w-0 truncate font-serif text-[20px] font-medium tracking-wide text-ink">{title}</h2>
        <ChevronDown size={14} strokeWidth={1.7} className={clsx('shrink-0 text-sepia-muted transition-transform duration-300', open && 'rotate-180')} />
      </button>
      <Popover open={open} onClose={close} side="down" className="w-[200px]" testId="title-popover">
        {page === 'main' ? (
          <>
            <MenuItem icon={menu.starred ? StarOff : Star} label={menu.starred ? t('取消星标') : t('星标')} onClick={() => (close(), menu.onStar())} />
            <MenuItem icon={Pencil} label={t('重命名')} onClick={() => (close(), menu.onRename())} />
            <MenuItem icon={FolderPlus} label={menu.projectId ? t('更换项目') : t('加入项目')} testId="title-project" onClick={() => setPage('project')} />
            <MenuDivider />
            <MenuItem icon={Trash2} label={t('删除')} danger onClick={() => (close(), menu.onDelete())} />
          </>
        ) : (
          <ProjectPicker menu={menu} onBack={() => setPage('main')} onDone={close} />
        )}
      </Popover>
    </div>
  )
}

function ShareButton({ actions }: { actions: ShareActions }) {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  return (
    <div className="relative">
      <button
        type="button"
        data-testid="share"
        onClick={() => setOpen((o) => !o)}
        className={clsx('chip transition-colors duration-300 hover:text-amber-ink', open && 'text-amber-ink')}
      >
        <Share size={11} strokeWidth={1.7} />
        {t('分享')}
      </button>
      <Popover open={open} onClose={close} side="down" align="right" className="w-[236px]" testId="share-popover">
        <p className="px-3 pb-1.5 pt-1 text-[11.5px] leading-relaxed text-sepia-muted">{t('只在本机：不上传、不生成公开链接')}</p>
        <MenuItem icon={ClipboardCopy} label={t('复制为 Markdown')} testId="share-copy" onClick={() => (close(), actions.copyMarkdown())} />
        <MenuDivider />
        <MenuItem icon={FileDown} label={t('导出为 Markdown')} testId="share-md" onClick={() => (close(), actions.exportMarkdown())} />
        <MenuItem icon={Printer} label={t('导出为 PDF')} testId="share-pdf" onClick={() => (close(), actions.exportPdf())} />
      </Popover>
    </div>
  )
}
