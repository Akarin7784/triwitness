import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { isEditable } from '../lib/desktopGuards'
import { t as tr } from '../lib/i18n'

type Action = 'cut' | 'copy' | 'paste' | 'selectAll'

interface MenuState {
  x: number
  y: number
  target: HTMLElement
  editable: boolean
  hasSelection: boolean
}

const ITEMS: { id: Action; label: string; keys: string }[] = [
  { id: 'cut', label: tr('剪切'), keys: 'Ctrl X' },
  { id: 'copy', label: tr('复制'), keys: 'Ctrl C' },
  { id: 'paste', label: tr('粘贴'), keys: 'Ctrl V' },
  { id: 'selectAll', label: tr('全选'), keys: 'Ctrl A' },
]

function selectionIn(el: HTMLElement): string {
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    return el.value.slice(el.selectionStart ?? 0, el.selectionEnd ?? 0)
  }
  return window.getSelection()?.toString() ?? ''
}

/**
 * 自绘右键菜单：只在输入框、或已选中可选文字（消息 / 推流）时出现。
 * 其它位置右键什么也不发生（默认菜单已被全局屏蔽）。
 */
export function ContextMenu() {
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const [active, setActive] = useState(-1)
  const ref = useRef<HTMLDivElement>(null)

  const close = useCallback(() => {
    setMenu(null)
    setPos(null)
    setActive(-1)
  }, [])

  useEffect(() => {
    const onContext = (e: MouseEvent) => {
      if (import.meta.env.DEV && e.shiftKey) return
      const target = e.target instanceof HTMLElement ? e.target : null
      if (!target) return close()
      const editable = isEditable(target)
      const sel = window.getSelection()
      const hasDomSelection =
        !!sel && !sel.isCollapsed && !!sel.anchorNode && !!target.closest('.selectable')?.contains(sel.anchorNode)
      if (!editable && !hasDomSelection) return close()
      setMenu({
        x: e.clientX,
        y: e.clientY,
        target,
        editable,
        hasSelection: editable ? selectionIn(target).length > 0 : hasDomSelection,
      })
      setActive(-1)
    }
    window.addEventListener('contextmenu', onContext)
    return () => window.removeEventListener('contextmenu', onContext)
  }, [close])

  // 位置限制在窗口内
  useLayoutEffect(() => {
    if (!menu || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const pad = 8
    const left = Math.min(menu.x, window.innerWidth - r.width - pad)
    const top = menu.y + r.height + pad > window.innerHeight ? Math.max(pad, menu.y - r.height) : menu.y
    setPos({ left: Math.max(pad, left), top })
  }, [menu])

  const enabled = useCallback(
    (id: Action) => {
      if (!menu) return false
      if (id === 'copy') return menu.hasSelection
      if (id === 'cut') return menu.editable && menu.hasSelection
      if (id === 'paste') return menu.editable
      return true
    },
    [menu],
  )

  const run = useCallback(
    async (id: Action) => {
      if (!menu || !enabled(id)) return
      const t = menu.target
      close()
      if (menu.editable) t.focus()
      try {
        if (id === 'copy') {
          const text = selectionIn(t)
          if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text)
          else document.execCommand('copy')
        } else if (id === 'cut') {
          const text = selectionIn(t)
          if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text)
          // insertText 会触发 input 事件（React 受控组件同步），并保留撤销栈
          document.execCommand('insertText', false, '')
        } else if (id === 'paste') {
          const text = await navigator.clipboard.readText()
          if (text) document.execCommand('insertText', false, text)
        } else if (id === 'selectAll') {
          if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) t.select()
          else {
            const host = t.closest('.selectable')
            if (host) window.getSelection()?.selectAllChildren(host)
          }
        }
      } catch {
        /* 剪贴板权限被拒时静默 */
      }
    },
    [menu, enabled, close],
  )

  // 键盘：Esc 关闭，↑↓ 选择，Enter 执行；点外部、滚动、失焦、改窗口大小都关闭
  useEffect(() => {
    if (!menu) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        close()
      } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const dir = e.key === 'ArrowDown' ? 1 : -1
        setActive((cur) => {
          let i = cur
          for (let n = 0; n < ITEMS.length; n++) {
            i = (i + dir + ITEMS.length) % ITEMS.length
            if (enabled(ITEMS[i].id)) return i
          }
          return cur
        })
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault()
        run(ITEMS[active].id)
      }
    }
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close()
    }
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('mousedown', onDown, true)
    window.addEventListener('resize', close)
    window.addEventListener('blur', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('mousedown', onDown, true)
      window.removeEventListener('resize', close)
      window.removeEventListener('blur', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [menu, active, enabled, run, close])

  if (!menu) return null
  return (
    <div
      ref={ref}
      role="menu"
      className="ctx-menu"
      style={{ left: pos?.left ?? menu.x, top: pos?.top ?? menu.y, visibility: pos ? 'visible' : 'hidden' }}
      onContextMenu={(e) => e.preventDefault()}
    >
      {ITEMS.map((it, i) => {
        const on = enabled(it.id)
        return (
          <button
            key={it.id}
            type="button"
            role="menuitem"
            disabled={!on}
            onMouseEnter={() => on && setActive(i)}
            onMouseLeave={() => setActive(-1)}
            onMouseDown={(e) => e.preventDefault() /* 不抢走输入框的选区 */}
            onClick={() => run(it.id)}
            className={clsx('ctx-item', active === i && 'ctx-item-active', it.id === 'selectAll' && 'ctx-item-sep')}
          >
            <span>{it.label}</span>
            <span className="ctx-keys">{it.keys}</span>
          </button>
        )
      })}
    </div>
  )
}
