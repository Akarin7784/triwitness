import { FIXTURE_NAMES, type FixtureName } from '../data/sources/fixture'

/** ?source=fixture:success | fixture:failure | fixture:budget_exceeded | mock；默认 fixture:success */
export type SourceKey = `fixture:${FixtureName}` | 'mock' | `local:${string}`

export function parseSourceParam(search: string): SourceKey {
  const raw = new URLSearchParams(search).get('source') ?? ''
  if (raw === 'mock') return 'mock'
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
