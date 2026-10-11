/** 外部打开（v0.3）：桌面端走 tauri-plugin-opener，浏览器预览退回 window.open；失败返回 false，由调用方提示 */
import { inTauri } from './appWindow'

export const RELEASES_URL = 'https://github.com/Akarin7784/triwitness/releases'

export async function openUrl(url: string): Promise<boolean> {
  try {
    if (inTauri) {
      const { openUrl: open } = await import('@tauri-apps/plugin-opener')
      await open(url)
    } else {
      window.open(url, '_blank', 'noopener')
    }
    return true
  } catch {
    return false
  }
}

/** 在资源管理器里定位文件夹 / 文件（只在桌面端可用） */
export async function revealPath(path: string): Promise<boolean> {
  if (!inTauri || !path) return false
  try {
    const { revealItemInDir } = await import('@tauri-apps/plugin-opener')
    await revealItemInDir(path)
    return true
  } catch {
    return false
  }
}
