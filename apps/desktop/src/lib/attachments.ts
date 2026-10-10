/**
 * 附件（UI-21 第 3 轮）：+ 菜单 / 拖放 / 粘贴 / Ctrl+U 选文件 → 落盘到 ~/.triwitness/attachments/ → 随任务交给核心。
 * 文本内联进任务描述；图片与二进制只附文件名（DeepSeek Flash 只读文字），界面如实提示。
 */
import { getTransport } from '../bridge/transport'

export type AttachKind = 'text' | 'image' | 'binary'
export interface Attachment {
  id: string
  name: string
  size: number
  kind: AttachKind
  status: 'saving' | 'ready' | 'error'
  /** 落盘路径（ready 后才有） */
  path?: string
  /** 图片缩略图（object URL） / 文本前几行 */
  preview?: string
  error?: string
}

export const MAX_FILE_BYTES = 10 * 1024 * 1024
export const MAX_FILES = 20
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|heic|tiff?)$/i
const TEXT_EXT =
  /\.(txt|md|markdown|py|js|jsx|ts|tsx|json|ya?ml|toml|ini|cfg|csv|tsv|html?|css|scss|rs|go|java|kt|c|h|cc|cpp|hpp|cs|rb|php|sh|bash|ps1|bat|sql|xml|log|diff|patch|env\.example|gitignore|dockerfile|lock|vue|svelte|swift|lua|r|m|ipynb)$/i

export function classify(name: string, mime = ''): AttachKind {
  if (mime.startsWith('image/') || IMAGE_EXT.test(name)) return 'image'
  if (mime.startsWith('text/') || TEXT_EXT.test(name) || /^(Makefile|Dockerfile|README|LICENSE)$/i.test(name)) return 'text'
  if (/json|xml|yaml|javascript|typescript/.test(mime)) return 'text'
  return 'binary'
}

export function formatSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function bytesToB64(bytes: Uint8Array): string {
  let s = ''
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(s)
}

export function textToB64(text: string): string {
  return bytesToB64(new TextEncoder().encode(text))
}

let n = 0
export function newAttachment(file: File): Attachment {
  const kind = classify(file.name, file.type)
  return {
    id: `att-${Date.now().toString(36)}-${++n}`,
    name: file.name || (kind === 'image' ? `粘贴的图片-${n}.png` : `文件-${n}`),
    size: file.size,
    kind,
    status: file.size > MAX_FILE_BYTES ? 'error' : 'saving',
    error: file.size > MAX_FILE_BYTES ? '超过 10 MB' : undefined,
    preview: kind === 'image' && typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(file) : undefined,
  }
}

/** 读文件 → 交给后端落盘；没有核心（纯浏览器预览）时只在界面上显示，发送时不带 */
export async function saveFile(file: File, a: Attachment): Promise<Attachment> {
  if (a.status === 'error') return a
  try {
    const bytes = new Uint8Array(await file.arrayBuffer())
    const preview = a.kind === 'text' ? new TextDecoder().decode(bytes.subarray(0, 4096)) : a.preview
    const t = await getTransport()
    if (!t) return { ...a, status: 'error', error: '未连接核心，无法附上', preview }
    const saved = await t.saveAttachment(a.name, bytesToB64(bytes))
    return { ...a, status: 'ready', path: saved.path, name: saved.name, preview }
  } catch (e) {
    return { ...a, status: 'error', error: String(e instanceof Error ? e.message : e) }
  }
}

/** 拖放 / 粘贴 / 文件选择都走这个事件，输入框接住 */
export const ATTACH_EVENT = 'tw:attach-files'
export function dispatchFiles(files: File[]) {
  if (files.length) window.dispatchEvent(new CustomEvent<File[]>(ATTACH_EVENT, { detail: files }))
}
