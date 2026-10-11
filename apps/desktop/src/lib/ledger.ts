/**
 * 真实账本（v0.3）：经白名单命令 `tw budget --json` 读 ~/.triwitness/ledger.sqlite（只读、不联网）。
 * 预算页和状态栏共用一份缓存；30 秒或窗口重新可见时刷新。没连上核心时返回 offline，界面显示“—”，不编数字。
 */
import { useSyncExternalStore } from 'react'
import { coreTool } from './coreTool'

export interface LedgerCall {
  ts: string // 北京时间 MM-DD HH:mm
  category: string
  task_id: string | null
  model: string
  peak: boolean
  input_tokens: number
  cache_hit_tokens: number
  cache_miss_tokens: number
  output_tokens: number
  cost_cny: number
}

export interface BudgetData {
  now: string
  total_cny: number
  spent: number
  remaining: number
  calls: number
  peak_calls: number
  cache_hit_rate: number | null
  warn: boolean
  kill_switch: boolean
  burn_per_day: number | null
  exhaustion: string | null
  envelopes: { category: string; spent: number; cap: number | null; remaining: number | null }[]
  by_week: Record<string, number>
  by_model: Record<string, number>
  recent: LedgerCall[]
}

export type LedgerState =
  | { status: 'loading' }
  | { status: 'ok'; data: BudgetData }
  | { status: 'offline' }
  | { status: 'error'; error: string }

let state: LedgerState = { status: 'loading' }
const subs = new Set<() => void>()
let timer: number | undefined
let inflight = false

export const getLedgerState = () => state

export function setLedgerState(s: LedgerState) {
  state = s
  subs.forEach((f) => f())
}

export async function refreshLedger() {
  if (inflight) return
  inflight = true
  try {
    const r = await coreTool<BudgetData>(['budget', '--json'])
    if (r.ok) setLedgerState({ status: 'ok', data: r.data })
    else setLedgerState(r.offline ? { status: 'offline' } : { status: 'error', error: r.error })
  } finally {
    inflight = false
  }
}

function onVisible() {
  if (document.visibilityState === 'visible') void refreshLedger()
}

function subscribe(f: () => void) {
  subs.add(f)
  if (subs.size === 1) {
    void refreshLedger()
    timer = window.setInterval(() => document.visibilityState === 'visible' && void refreshLedger(), 30_000)
    document.addEventListener('visibilitychange', onVisible)
  }
  return () => {
    subs.delete(f)
    if (subs.size === 0) {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }
}

export function useLedger(): LedgerState {
  return useSyncExternalStore(subscribe, getLedgerState)
}

/** 一行调用的缓存命中率（无输入时为 null） */
export function hitRate(c: Pick<LedgerCall, 'input_tokens' | 'cache_hit_tokens'>): number | null {
  return c.input_tokens ? c.cache_hit_tokens / c.input_tokens : null
}
