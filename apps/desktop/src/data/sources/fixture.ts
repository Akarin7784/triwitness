import { parseJsonl, type AnyEvent } from '../events'
import type { EventSource, SubscribeOptions } from './types'

export interface FixtureOptions {
  /** 回放倍速，默认 1.5 */
  speed?: number
  /** 两个事件之间最长等待（毫秒，倍速换算后），避免长时间空白 */
  maxGapMs?: number
  /** 第一条事件前的等待 */
  leadMs?: number
  /** 测试注入 */
  setTimer?: (fn: () => void, ms: number) => unknown
  clearTimer?: (h: unknown) => void
}

/**
 * 按事件 ts 差值回放 JSONL。
 * load 只调用一次（懒加载：打包时 fixture 被拆成独立 chunk）。
 */
export class FixtureSource implements EventSource {
  readonly id: string
  private loading: Promise<AnyEvent[]> | null = null
  private timers = new Set<unknown>()
  private closed = false
  private _afterSeq = -1

  private readonly load: () => Promise<string>
  private readonly opts: FixtureOptions

  constructor(id: string, load: () => Promise<string>, opts: FixtureOptions = {}) {
    this.id = id
    this.load = load
    this.opts = opts
  }

  get afterSeq() {
    return this._afterSeq
  }

  private ensure(): Promise<AnyEvent[]> {
    this.loading ??= this.load().then(parseJsonl)
    return this.loading
  }

  subscribe(onEvent: (e: AnyEvent) => void, sub: SubscribeOptions = {}) {
    const set = this.opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms))
    const clear = this.opts.clearTimer ?? ((h) => clearTimeout(h as number))
    const speed = this.opts.speed ?? 1.5
    const maxGap = this.opts.maxGapMs ?? 3200
    const lead = this.opts.leadMs ?? 300
    let active = true
    const mine = new Set<unknown>()

    this.ensure().then((all) => {
      if (!active || this.closed) return
      const list = all.filter((e) => e.seq > (sub.afterSeq ?? -1))
      let at = lead
      let prevTs: number | null = null
      for (const e of list) {
        const t = Date.parse(e.ts)
        if (prevTs !== null) at += Math.min(Math.max(0, (t - prevTs) / speed), maxGap)
        prevTs = t
        const h = set(() => {
          mine.delete(h)
          this.timers.delete(h)
          if (!active || this.closed) return
          this._afterSeq = Math.max(this._afterSeq, e.seq)
          onEvent(e)
        }, at)
        mine.add(h)
        this.timers.add(h)
      }
    })

    return () => {
      active = false
      for (const h of mine) {
        clear(h)
        this.timers.delete(h)
      }
    }
  }

  close() {
    this.closed = true
    const clear = this.opts.clearTimer ?? ((h) => clearTimeout(h as number))
    for (const h of this.timers) clear(h)
    this.timers.clear()
  }
}

/** 仓库根 evals/fixtures/events 下的 golden fixture（单一来源，不复制） */
const LOADERS = {
  success: () => import('../../../../../evals/fixtures/events/success.jsonl?raw').then((m) => m.default),
  failure: () => import('../../../../../evals/fixtures/events/failure.jsonl?raw').then((m) => m.default),
  budget_exceeded: () =>
    import('../../../../../evals/fixtures/events/budget_exceeded.jsonl?raw').then((m) => m.default),
  /** core 的 TrajectoryRecorder 真实写出（W1-24），保证 core 与 UI 同形 */
  recorded: () => import('../../../../../evals/fixtures/events/recorded.jsonl?raw').then((m) => m.default),
} as const

/** 录好的轨迹回放只在开发构建里有（0.3.1 起正式版不打包 fixture，侧栏也不列） */
export const FIXTURES: typeof LOADERS = import.meta.env.DEV ? LOADERS : ({} as typeof LOADERS)
export type FixtureName = keyof typeof LOADERS
export const FIXTURE_NAMES = Object.keys(FIXTURES) as FixtureName[]
