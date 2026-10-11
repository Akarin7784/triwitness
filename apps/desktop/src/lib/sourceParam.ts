import { FIXTURE_NAMES, type FixtureName } from '../data/sources/fixture'

/** ?source=fixture:success | fixture:failure | fixture:budget_exceeded | fixture:recorded | mock；默认 fixture:success */
export type SourceKey = `fixture:${FixtureName}` | 'mock' | 'stress' | `local:${string}` | `live:${string}`

export function parseSourceParam(search: string): SourceKey {
  const raw = new URLSearchParams(search).get('source') ?? ''
  if (raw === 'mock') return 'mock'
  if (raw === 'stress') return 'stress'
  if (/^live:[\w-]+$/.test(raw)) return raw as SourceKey
  const m = /^fixture:(.+)$/.exec(raw)
  if (m && (FIXTURE_NAMES as string[]).includes(m[1])) return `fixture:${m[1] as FixtureName}`
  return 'fixture:success'
}

export function writeSourceParam(key: SourceKey) {
  if (key.startsWith('local:')) return
  const url = new URL(window.location.href)
  url.searchParams.set('source', key)
  window.history.replaceState(null, '', url)
}

export function speedParam(search: string): number | undefined {
  const s = Number(new URLSearchParams(search).get('speed'))
  return Number.isFinite(s) && s > 0 ? s : undefined
}

/** ?rounds=N / ?repeat=K（压测源参数，1–2000） */
export function roundsParam(search: string, name = 'rounds', fallback = 60): number {
  const n = Math.floor(Number(new URLSearchParams(search).get(name)))
  return Number.isFinite(n) && n >= 1 ? Math.min(n, 2000) : fallback
}
