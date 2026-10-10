import { useCallback, useEffect, useRef, useState } from 'react'
import type { StreamLine } from '../types'

/**
 * 书写感推流引擎
 * - 虚拟时钟：只在播放时前进（暂停 = 时钟冻结，不丢字也不补跳）
 * - 时序确定、平滑：用字符哈希做 ±小幅变化，不用 Math.random，避免抖动感
 * - 停顿像人落笔：标点后稍歇、行末换气、词间微顿、长行中途偶尔沉吟
 * - 支持流式追加：lines 只追加时，新字接在队尾继续写；被替换时整体重置
 * - prefers-reduced-motion：整行一次出现，行间短停顿
 */

export interface WrittenChar {
  key: string
  ch: string
  at: number
  lineId: string
  role: StreamLine['role']
}

const PAUSE_AFTER_STRONG = '。！？!?'
const PAUSE_AFTER_SOFT = '，、；：,;:·…—）〕)'
const LINE_END_BREATH = 380

function hash01(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 1000) / 1000
}

function isCjk(ch: string) {
  const c = ch.codePointAt(0) ?? 0
  return c >= 0x2e80
}

/** 写完当前字后，到下一个字落笔需要等多久 */
function gapAfter(ch: string, next: string | undefined, i: number, lineId: string): number {
  // 平滑变化：基于位置的缓慢正弦 + 哈希微扰，幅度小，读起来是“呼吸”而非“抖”
  const wave = Math.sin(i / 6) * 0.12
  const wobble = (hash01(lineId + i) - 0.5) * 0.16
  const k = 1 + wave + wobble
  if (PAUSE_AFTER_STRONG.includes(ch)) return 260 * k
  if (PAUSE_AFTER_SOFT.includes(ch)) return 150 * k
  if (ch === ' ') return 46 * k
  if (next === ' ' || next === '/' || next === '.') return 40 * k
  // 长行中途偶尔停笔想一想（确定性，每行最多一两次）
  if (i > 12 && hash01(lineId + 'p' + i) > 0.965) return 190 * k
  return (isCjk(ch) ? 52 : 30) * k
}

export function schedule(
  lines: StreamLine[],
  startAt: number,
  reduced: boolean,
): { chars: WrittenChar[]; endAt: number } {
  const out: WrittenChar[] = []
  let t = startAt
  for (const line of lines) {
    t += reduced ? 120 : (line.pauseBefore ?? 0)
    const glyphs = Array.from(line.text)
    glyphs.forEach((ch, i) => {
      out.push({ key: `${line.id}-${i}`, ch, at: t, lineId: line.id, role: line.role })
      if (!reduced) t += gapAfter(ch, glyphs[i + 1], i, line.id)
    })
    t += reduced ? 0 : LINE_END_BREATH
  }
  return { chars: out, endAt: t }
}

export interface UseWritingStreamOptions {
  lines: StreamLine[]
  autoStart?: boolean
  reducedMotion?: boolean
  /** 播放速度倍率，1 = 默认 */
  speed?: number
}

export function useWritingStream({
  lines,
  autoStart = true,
  reducedMotion = false,
  speed = 1,
}: UseWritingStreamOptions) {
  const [visibleCount, setVisibleCount] = useState(0)
  const [playing, setPlaying] = useState(autoStart)
  // 渲染只读 state；ref 只在 effect / 回调 / rAF 里读写（react(refs) 规则）
  const [chars, setChars] = useState<WrittenChar[]>([])

  const charsRef = useRef<WrittenChar[]>([])
  const endAtRef = useRef(0)
  const linesSeenRef = useRef<StreamLine[]>([])
  const clockRef = useRef(0)
  const visibleRef = useRef(0)
  const speedRef = useRef(speed)
  useEffect(() => {
    speedRef.current = speed
  }, [speed])

  const reset = useCallback(() => {
    charsRef.current = []
    endAtRef.current = 0
    linesSeenRef.current = []
    clockRef.current = 0
    visibleRef.current = 0
    setVisibleCount(0)
    setChars([])
  }, [])

  // 处理 lines 变化：追加 or 重置
  useEffect(() => {
    const seen = linesSeenRef.current
    const isAppend =
      lines.length >= seen.length && seen.every((l, i) => lines[i]?.id === l.id)
    if (!isAppend) reset()
    const fresh = lines.slice(isAppend ? seen.length : 0)
    if (fresh.length === 0) return
    const startAt = Math.max(endAtRef.current, clockRef.current)
    const { chars: added, endAt } = schedule(fresh, startAt, reducedMotion)
    const next = charsRef.current.concat(added)
    charsRef.current = next
    endAtRef.current = endAt
    linesSeenRef.current = lines.slice()
    setChars(next)
  }, [lines, reducedMotion, reset])

  // 虚拟时钟
  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    const frame = (now: number) => {
      const dt = Math.min(now - last, 64) // 切后台回来不突然倾泻
      last = now
      clockRef.current += dt * speedRef.current
      const all = charsRef.current
      let n = visibleRef.current
      while (n < all.length && all[n].at <= clockRef.current) n++
      if (n !== visibleRef.current) {
        visibleRef.current = n
        setVisibleCount(n)
      }
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [playing])

  const total = chars.length
  const done = total > 0 && visibleCount >= total

  const restart = useCallback(() => {
    const keep = linesSeenRef.current
    reset()
    const { chars: replay, endAt } = schedule(keep, 0, reducedMotion)
    charsRef.current = replay
    endAtRef.current = endAt
    linesSeenRef.current = keep
    setPlaying(true)
    setChars(replay)
  }, [reset, reducedMotion])

  const toggle = useCallback(() => {
    if (done) return restart()
    setPlaying((p) => !p)
  }, [done, restart])

  return {
    chars,
    visibleCount,
    playing,
    done,
    toggle,
    restart,
    pause: () => setPlaying(false),
    resume: () => setPlaying(true),
    progress: total ? visibleCount / total : 0,
  }
}
