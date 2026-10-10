/**
 * 桌面应用防护：屏蔽浏览器式行为。
 * 原生层（Windows release）另外关闭了 WebView2 的浏览器快捷键与默认菜单，见 src-tauri/src/lib.rs；
 * 这里是第二道保险，同时覆盖浏览器预览。
 *
 * 开发期例外：DEV 模式下按住 Shift 右键，放行原生菜单（用于“检查元素”）；F12 / Ctrl+Shift+I 仅 DEV 放行。
 */

const DEV = import.meta.env.DEV

export function isEditable(el: EventTarget | null): el is HTMLInputElement | HTMLTextAreaElement | HTMLElement {
  if (!(el instanceof HTMLElement)) return false
  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled
  if (el instanceof HTMLInputElement) {
    const textual = ['text', 'search', 'url', 'email', 'tel', 'password', 'number', ''].includes(el.type)
    return textual && !el.readOnly && !el.disabled
  }
  return el.isContentEditable
}

function blockedKey(e: KeyboardEvent): boolean {
  const k = e.key.toLowerCase()
  const ctrl = e.ctrlKey || e.metaKey
  // 刷新 / 打印 / 查找 / 源码 / 光标浏览 / 保存 / 历史 / 下载 / 新窗口 / 新标签
  if (k === 'f5' || k === 'f7' || k === 'f3') return true
  if (ctrl && ['r', 'p', 'f', 'g', 'u', 's', 'h', 'j', 'n', 't'].includes(k)) return true
  // 缩放
  if (ctrl && ['=', '+', '-', '_', '0'].includes(k)) return true
  // 前进 / 后退
  if (e.altKey && (k === 'arrowleft' || k === 'arrowright')) return true
  if (k === 'browserback' || k === 'browserforward' || k === 'browserrefresh' || k === 'browsersearch') return true
  // 开发者工具（仅 release 屏蔽）
  if (!DEV && (k === 'f12' || (ctrl && e.shiftKey && ['i', 'j', 'c'].includes(k)))) return true
  // 非输入区的全选：避免整页 UI 被选中
  if (ctrl && k === 'a' && !isEditable(e.target)) return true
  return false
}

let installed = false

export function installDesktopGuards() {
  if (installed) return
  installed = true

  // 默认右键菜单：一律屏蔽（自绘菜单在 ContextMenu 组件里处理）
  window.addEventListener(
    'contextmenu',
    (e) => {
      if (DEV && e.shiftKey) return
      e.preventDefault()
    },
    { capture: true },
  )

  window.addEventListener(
    'keydown',
    (e) => {
      if (blockedKey(e)) {
        e.preventDefault()
        e.stopPropagation()
      }
    },
    { capture: true },
  )

  // Ctrl + 滚轮缩放、触控板捏合
  window.addEventListener(
    'wheel',
    (e) => {
      if (e.ctrlKey) e.preventDefault()
    },
    { passive: false, capture: true },
  )

  // 拖入文件 / 链接不让 WebView 打开；拖出图片、链接也禁止
  const stopDrop = (e: DragEvent) => {
    if (!(e.target instanceof Element) || !e.target.closest('[data-dropzone]')) {
      e.preventDefault()
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'none'
    }
  }
  window.addEventListener('dragover', stopDrop, { capture: true })
  window.addEventListener('drop', stopDrop, { capture: true })
  window.addEventListener(
    'dragstart',
    (e) => {
      const t = e.target
      if (t instanceof HTMLImageElement || t instanceof HTMLAnchorElement || (t instanceof Element && t.closest('svg'))) {
        e.preventDefault()
      }
    },
    { capture: true },
  )

  // 鼠标中键自动滚动 / 中键打开链接
  window.addEventListener(
    'auxclick',
    (e) => {
      if (e.button === 1) e.preventDefault()
    },
    { capture: true },
  )
  window.addEventListener(
    'mousedown',
    (e) => {
      if (e.button === 1) e.preventDefault()
    },
    { capture: true },
  )
}
