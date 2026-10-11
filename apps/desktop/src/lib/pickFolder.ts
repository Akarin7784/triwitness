import { inTauri } from '../bridge/transport'

/**
 * 原生“选择文件夹”（BUG2）：Tauri 里用 dialog 插件；浏览器 / 开发桥里没有原生对话框，返回 undefined，
 * 由调用方退回手动输入。取消返回 null。
 */
export async function pickFolder(defaultPath?: string): Promise<string | null | undefined> {
  if (!inTauri()) return undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ directory: true, multiple: false, defaultPath: defaultPath || undefined, title: undefined })
  return typeof r === 'string' ? r : null
}

/** 路径最后一段（chip 上显示），完整路径放提示里 */
export function baseName(p: string): string {
  const parts = p.replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] || p
}
