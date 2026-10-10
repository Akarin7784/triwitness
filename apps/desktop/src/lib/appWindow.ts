import { isTauri } from '@tauri-apps/api/core'
import type { Window } from '@tauri-apps/api/window'

/** 浏览器预览里没有 Tauri：所有窗口操作安静地什么都不做 */
export const inTauri = isTauri()

let cached: Promise<Window> | null = null
function win(): Promise<Window> | null {
  if (!inTauri) return null
  cached ??= import('@tauri-apps/api/window').then((m) => m.getCurrentWindow())
  return cached
}

export const appWindow = {
  minimize: () => win()?.then((w) => w.minimize()).catch(() => {}),
  toggleMaximize: () => win()?.then((w) => w.toggleMaximize()).catch(() => {}),
  close: () => win()?.then((w) => w.close()).catch(() => {}),
  isMaximized: async () => (await win()?.then((w) => w.isMaximized()).catch(() => false)) ?? false,
  onResized: async (cb: () => void) => {
    const w = await win()
    if (!w) return () => {}
    return w.onResized(cb)
  },
}
