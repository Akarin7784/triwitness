import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, FileText, FolderClosed, Loader2, MessageSquarePlus, Pencil, Plus, Trash2, Upload, X } from 'lucide-react'
import clsx from 'clsx'
import {
  addKnowledge,
  createProject,
  deleteProject,
  removeKnowledge,
  updateProject,
  useProjects,
  type Project,
} from '../lib/projects'
import { formatSize, newAttachment, saveFile } from '../lib/attachments'
import { toast } from '../lib/toast'
import { FIELD } from '../lib/ui'
import { Btn, Dialog, DialogActions } from './Dialog'
import { ConfirmDeleteDialog, RenameDialog } from './ChatDialogs'
import { locale, t as tr } from '../lib/i18n'

export interface ProjectChat {
  id: string
  title: string
  time?: string
}

const SPRING = { type: 'spring', stiffness: 420, damping: 36 } as const

/** 项目（照 Claude Projects）：列表 → 详情（会话 · 说明 · 知识文件） */
export function ProjectsPage({
  selected,
  onSelect,
  chatsOf,
  onOpenChat,
  onNewChat,
}: {
  selected: string | null
  onSelect: (id: string | null) => void
  chatsOf: (pid: string) => ProjectChat[]
  onOpenChat: (id: string) => void
  onNewChat: (pid: string) => void
}) {
  const { projects } = useProjects()
  const project = projects.find((p) => p.id === selected)
  return (
    <main data-testid="projects-page" className="min-w-0 flex-1 overflow-y-auto scroll-soft">
      <AnimatePresence mode="wait" initial={false}>
        {project ? (
          <motion.div key={project.id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ pointerEvents: 'none', opacity: 0, x: -12 }} transition={SPRING}>
            <ProjectDetail project={project} chats={chatsOf(project.id)} onBack={() => onSelect(null)} onOpenChat={onOpenChat} onNewChat={() => onNewChat(project.id)} />
          </motion.div>
        ) : (
          <motion.div key="list" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ pointerEvents: 'none', opacity: 0, x: 12 }} transition={SPRING}>
            <ProjectList projects={projects} chatsOf={chatsOf} onSelect={onSelect} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  )
}

function ProjectList({ projects, chatsOf, onSelect }: { projects: Project[]; chatsOf: (pid: string) => ProjectChat[]; onSelect: (id: string) => void }) {
  const [creating, setCreating] = useState(false)
  const [q, setQ] = useState('')
  const shown = projects.filter((p) => !q.trim() || p.name.includes(q.trim()) || p.description.includes(q.trim()))
  return (
    <div className="mx-auto max-w-[860px] px-12 py-10">
      <div className="flex items-center justify-between">
        <h1 className="chapter-title font-serif text-[26px] text-ink">{tr('项目')}</h1>
        <Btn kind="solid" onClick={() => setCreating(true)} testId="project-new">
          <span className="inline-flex items-center gap-1.5">
            <Plus size={14} /> {tr('新建项目')}
          </span>
        </Btn>
      </div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={tr('搜索项目…')} aria-label={tr('搜索项目')} className={clsx(FIELD, 'mt-6')} />
      {projects.length === 0 ? (
        <div className="mt-16 flex flex-col items-center text-center">
          <FolderClosed size={28} strokeWidth={1.3} className="text-sepia-muted" />
          <p className="mt-3 font-serif text-[16px] text-ink">{tr('还没有项目')}</p>
          <p className="mt-1 max-w-[360px] text-[13px] leading-relaxed text-sepia-muted">{tr('把相关会话、说明和资料放在一起；项目里的每次任务都会带上它们。')}</p>
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {shown.map((p) => (
            <motion.button
              key={p.id}
              layout
              type="button"
              data-testid="project-card"
              onClick={() => onSelect(p.id)}
              className="paper-card rounded-2xl px-5 py-4 text-left transition-[border-color,transform] duration-300 hover:-translate-y-0.5 hover:border-border"
            >
              <p className="truncate font-serif text-[16px] text-ink">{p.name}</p>
              <p className="mt-1 line-clamp-2 min-h-[2.6em] text-[12.5px] leading-relaxed text-sepia">{p.description || '—'}</p>
              <p className="mt-3 text-[11px] text-sepia-muted">{tr('{0} 个会话 · {1} 个文件 · 更新于 {2}', chatsOf(p.id).length, p.knowledge.length, new Date(p.updatedAt).toLocaleDateString(locale()))}</p>
            </motion.button>
          ))}
        </div>
      )}
      <CreateDialog open={creating} onClose={() => setCreating(false)} onCreate={(name, desc) => onSelect(createProject(name, desc).id)} />
    </div>
  )
}

function CreateDialog({ open, onClose, onCreate }: { open: boolean; onClose: () => void; onCreate: (n: string, d: string) => void }) {
  return (
    <Dialog open={open} onClose={onClose} title={tr('新建项目')} width={480} testId="project-create">
      {open && <CreateBody onClose={onClose} onCreate={onCreate} />}
    </Dialog>
  )
}

function CreateBody({ onClose, onCreate }: { onClose: () => void; onCreate: (n: string, d: string) => void }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const go = () => {
    if (!name.trim()) return
    onCreate(name, desc)
    onClose()
  }
  return (
    <>
      <label htmlFor="pj-name" className="text-[12px] text-sepia-muted">
        {tr('名称')}
      </label>
      <input
        id="pj-name"
        autoFocus
        data-testid="project-name"
        value={name}
        maxLength={60}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent.isComposing && go()}
        className={clsx(FIELD, 'mt-1')}
      />
      <label htmlFor="pj-desc" className="mt-3 block text-[12px] text-sepia-muted">
        {tr('在做什么（可选）')}
      </label>
      <textarea id="pj-desc" value={desc} rows={3} maxLength={300} onChange={(e) => setDesc(e.target.value)} className={clsx(FIELD, 'mt-1 resize-none')} />
      <DialogActions>
        <Btn onClick={onClose}>{tr('取消')}</Btn>
        <Btn kind="solid" onClick={go} disabled={!name.trim()} testId="project-create-save">
          {tr('创建')}
        </Btn>
      </DialogActions>
    </>
  )
}

function ProjectDetail({
  project,
  chats,
  onBack,
  onOpenChat,
  onNewChat,
}: {
  project: Project
  chats: ProjectChat[]
  onBack: () => void
  onOpenChat: (id: string) => void
  onNewChat: () => void
}) {
  const [instr, setInstr] = useState(project.instructions)
  const [renaming, setRenaming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [uploading, setUploading] = useState(0)
  const file = useRef<HTMLInputElement>(null)
  const dirty = instr !== project.instructions

  const upload = async (files: File[]) => {
    setUploading((n) => n + files.length)
    const done = []
    for (const f of files) {
      const a = await saveFile(f, newAttachment(f))
      if (a.status === 'ready' && a.path) done.push({ name: a.name, path: a.path, size: a.size })
      else toast(tr('{0}：{1}', f.name, a.error ?? tr('失败')))
      setUploading((n) => n - 1)
    }
    if (done.length) {
      addKnowledge(project.id, done)
      toast(tr('已加入 {0} 个文件', done.length))
    }
  }

  return (
    <div className="mx-auto max-w-[980px] px-12 py-8">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 text-[12.5px] text-sepia transition-colors hover:text-amber-ink">
        <ArrowLeft size={13} /> {tr('全部项目')}
      </button>
      <div className="mt-3 flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 data-testid="project-title" className="truncate font-serif text-[26px] text-ink">
            {project.name}
          </h1>
          {project.description && <p className="mt-1 text-[13px] text-sepia">{project.description}</p>}
        </div>
        <Btn onClick={() => setRenaming(true)}>
          <span className="inline-flex items-center gap-1">
            <Pencil size={12} /> {tr('重命名')}
          </span>
        </Btn>
        <Btn onClick={() => setDeleting(true)} testId="project-delete">
          <span className="inline-flex items-center gap-1 text-rose-ink">
            <Trash2 size={12} /> {tr('删除')}
          </span>
        </Btn>
      </div>

      <div className="mt-7 grid gap-8 lg:grid-cols-[1fr_340px]">
        <section>
          <button
            type="button"
            data-testid="project-new-chat"
            onClick={onNewChat}
            className="paper-card flex w-full items-center gap-2.5 rounded-2xl px-4 py-3.5 text-left text-[13.5px] text-sepia transition-colors duration-300 hover:border-border hover:text-ink"
          >
            <MessageSquarePlus size={15} strokeWidth={1.6} className="text-amber-ink" />
            {tr('在这个项目里开新会话')}
          </button>
          <h2 className="mt-6 text-[11px] tracking-[0.14em] text-sepia-muted">{tr('会话')}</h2>
          {chats.length === 0 ? (
            <p className="mt-3 text-[13px] text-sepia-muted">{tr('还没有会话。也可以在会话的 … 菜单里“加入项目”。')}</p>
          ) : (
            <ul className="mt-2 divide-y divide-border-soft">
              {chats.map((c) => (
                <li key={c.id}>
                  <button type="button" data-testid="project-chat" onClick={() => onOpenChat(c.id)} className="flex w-full items-center gap-3 py-3 text-left transition-colors hover:text-amber-ink">
                    <span className="min-w-0 flex-1 truncate font-serif text-[14px] text-ink">{c.title}</span>
                    {c.time && <span className="font-mono text-[10.5px] text-sepia-muted">{c.time}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="space-y-6">
          <div className="paper-card rounded-2xl px-4 py-4">
            <div className="flex items-center justify-between">
              <h2 className="text-[13px] text-ink">{tr('项目说明')}</h2>
              {dirty && (
                <Btn kind="solid" onClick={() => (updateProject(project.id, { instructions: instr }), toast(tr('已保存')))} testId="project-instr-save">
                  {tr('保存')}
                </Btn>
              )}
            </div>
            <textarea
              data-testid="project-instructions"
              value={instr}
              onChange={(e) => setInstr(e.target.value)}
              rows={6}
              maxLength={4000}
              placeholder={tr('告诉三证这个项目的约定，例如：测试用 pytest；提交信息用中文。')}
              className={clsx(FIELD, 'mt-2 resize-y text-[13px] leading-relaxed')}
            />
          </div>
          <div
            className="paper-card rounded-2xl px-4 py-4"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              void upload([...e.dataTransfer.files])
            }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-[13px] text-ink">{tr('知识文件')}</h2>
              <button type="button" onClick={() => file.current?.click()} data-testid="project-upload" className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[12px] text-amber-ink hover:bg-panel-raised">
                {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />} {tr('添加')}
              </button>
              <input
                ref={file}
                type="file"
                multiple
                hidden
                data-testid="project-file-input"
                onChange={(e) => {
                  void upload([...(e.target.files ?? [])])
                  e.target.value = ''
                }}
              />
            </div>
            {project.knowledge.length === 0 ? (
              <p className="mt-2 text-[12px] leading-relaxed text-sepia-muted">{tr('拖文件到这里，或点“添加”。文本会随项目里的每次任务一起交给模型。')}</p>
            ) : (
              <ul className="mt-2 space-y-1">
                <AnimatePresence initial={false}>
                  {project.knowledge.map((k) => (
                    <motion.li
                      key={k.path}
                      layout
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, pointerEvents: 'none', height: 0 }}
                      transition={SPRING}
                      data-testid="knowledge-file"
                      className="group flex items-center gap-2 rounded-lg px-1.5 py-1.5 hover:bg-panel-raised/60"
                    >
                      <FileText size={13} strokeWidth={1.6} className="shrink-0 text-sepia" />
                      <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink-soft">{k.name}</span>
                      <span className="text-[10.5px] text-sepia-muted">{formatSize(k.size)}</span>
                      <button type="button" aria-label={tr('移除 {0}', k.name)} onClick={() => removeKnowledge(project.id, k.path)} className="rounded p-0.5 text-sepia-muted opacity-0 transition-opacity hover:text-rose-ink group-hover:opacity-100 focus-visible:opacity-100">
                        <X size={12} />
                      </button>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </div>
        </aside>
      </div>
      <RenameDialog open={renaming} initial={project.name} onClose={() => setRenaming(false)} onSave={(t) => updateProject(project.id, { name: t })} />
      <ConfirmDeleteDialog
        open={deleting}
        heading={tr('删除项目')}
        title={project.name}
        onClose={() => setDeleting(false)}
        onConfirm={() => {
          deleteProject(project.id)
          onBack()
          toast(tr('已删除项目（会话保留）'))
        }}
      />
    </div>
  )
}
