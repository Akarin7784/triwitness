import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import type { ResultMsg } from '../bridge/protocol'
import { inconclusiveAdvice, primaryArtifact } from './verdictAdvice'

const base = (extra: Partial<ResultMsg> = {}): ResultMsg => ({
  bridge: 'result', status: 'done', run_dir: '/r', branch: 'tw/1', backend: 'none', cost_cny: 0.264, steps: 9,
  reason: null, summary: 's', verdict: 'inconclusive', risk_level: 'L2', clean_env: 'verified', pr_md: null, ...extra,
}) as ResultMsg

describe('结论卡「证据不足」的下一步提示', () => {
  it('真实 run（鹈鹕 index.html）：复现已通过 + Issue 没写验收标准 → 点名产物', () => {
    const r = base({ repro_status: 'reproduced', claim_flags: ['issue_underspecified'], changed_files: ['tests/tw_repro/test_issue_1.py', 'index.html'] })
    expect(inconclusiveAdvice(r)).toBe(
      '复现测试已通过，但 Issue 没写验收标准，所以无法判定是否真的修好。补两三条验收标准后重新验证，或者直接打开 index.html 看一眼。',
    )
  })
  it('没有非测试产物时不编文件名', () => {
    const r = base({ repro_status: 'reproduced', claim_flags: ['issue_underspecified'], changed_files: ['tests/test_a.py'] })
    expect(inconclusiveAdvice(r)).toMatch(/或者直接看一眼改动。$/)
  })
  it('其他原因各有具体下一步', () => {
    expect(inconclusiveAdvice(base({ repro_status: 'inconclusive' }))).toMatch(/^复现测试在修复前就已通过/)
    expect(inconclusiveAdvice(base({ claim_flags: ['repro_missing'], repro_status: 'not_applicable' }))).toMatch(/^没有复现测试/)
    expect(inconclusiveAdvice(base({ claim_flags: ['repro_not_tied_to_issue'], repro_status: 'reproduced' }))).toMatch(/在 Issue 里没有出现/)
    expect(inconclusiveAdvice(base({ anticheat_flags: ['skip_or_xfail_added'] }))).toMatch(/skip \/ xfail/)
    expect(inconclusiveAdvice(base({ regression_blind: true }))).toMatch(/^回归测试一个都没跑通/)
    expect(inconclusiveAdvice(base({ claim_flags: ['claim_contradicts_open_risks'] }))).toMatch(/风险说明/)
    expect(inconclusiveAdvice(base({ review_status: 'inconclusive' }))).toMatch(/^评审没有给出结论/)
    expect(inconclusiveAdvice(base())).toMatch(/^证据还不够下结论/)
  })
  it('通过 / 未过不给提示', () => {
    expect(inconclusiveAdvice(base({ verdict: 'pass' }))).toBeNull()
    expect(inconclusiveAdvice(base({ verdict: 'fail' }))).toBeNull()
  })
  it('产物挑第一个非测试文件', () => {
    expect(primaryArtifact(['src/__tests__/a.ts', 'a.test.ts', 'pkg/foo_test.go', 'README.md'])).toBe('README.md')
    expect(primaryArtifact(undefined)).toBeNull()
  })
  it('结论卡仍显示「证据不足」，只追加提示', () => {
    const src = readFileSync(new URL('../components/ResultCard.tsx', import.meta.url), 'utf8')
    expect(src).toContain("inconclusive: { label: t('证据不足')")
    expect(src).toContain('data-testid="verdict-advice"')
  })
})
