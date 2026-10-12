import type { ResultMsg } from '../bridge/protocol'
import { t } from './i18n'

/** 测试 / 复现文件不算「产物」 */
const TEST_FILE = /(^|\/)(tests?|__tests__|spec)\/|(^|\/)test_[^/]*$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$/i

/** 用户能直接打开看的产物：补丁里第一个非测试文件 */
export function primaryArtifact(files: string[] | undefined): string | null {
  return files?.find((f) => !TEST_FILE.test(f)) ?? null
}

/**
 * 结论「证据不足」时的具体下一步（保留「证据不足」结论本身，只把原因和下一步说清楚）。
 * 按核心降级的原因给一句话：先说已经确认了什么，再说为什么无法判定，最后给一两个能做的动作。
 * 不是 inconclusive 返回 null。
 */
export function inconclusiveAdvice(r: ResultMsg): string | null {
  if (r.verdict !== 'inconclusive') return null
  const claims = new Set(r.claim_flags ?? [])
  const reproduced = r.repro_status === 'reproduced'
  const art = primaryArtifact(r.changed_files)
  const look = art ? t('或者直接打开 {0} 看一眼。', art) : t('或者直接看一眼改动。')
  if (claims.has('issue_underspecified')) {
    return reproduced
      ? t('复现测试已通过，但 Issue 没写验收标准，所以无法判定是否真的修好。补两三条验收标准后重新验证，') + look
      : t('Issue 没写验收标准，复现测试也没能证明问题，所以无法判定是否真的修好。补两三条验收标准后重新验证，') + look
  }
  if (r.repro_status === 'inconclusive')
    return t('复现测试在修复前就已通过，没能证明问题存在，所以无法判定是否真的修好。在 Issue 里补上能稳定触发问题的步骤或报错后重新验证。')
  if (claims.has('repro_missing'))
    return t('没有复现测试，没法证明问题修好前存在、修好后消失，所以无法判定。在 Issue 里写清报错或期望行为后重新验证，') + look
  if (claims.has('repro_not_tied_to_issue'))
    return t('复现测试已通过，但它检查的值在 Issue 里没有出现，测的可能不是你说的问题，所以无法判定。在 Issue 里写明期望的具体结果后重新验证，') + look
  if (r.anticheat_flags?.includes('skip_or_xfail_added'))
    return t('补丁新增了被跳过（skip / xfail）的测试，需要你确认这样做合理，所以无法判定。看一眼 pr.md 里跳过的原因，确认后再开 PR。')
  if (r.regression_blind)
    return t('回归测试一个都没跑通（多半是测试依赖没装好或命令不对），没有「没改坏别的」的证据，所以无法判定。装好测试依赖后重新验证。')
  if (claims.has('claim_contradicts_open_risks'))
    return t('测试都通过了，但 Agent 自己说有没覆盖或不确定的地方，所以无法判定。看一眼 pr.md 里的风险说明，能接受再开 PR。')
  if (r.review_status === 'inconclusive')
    return t('评审没有给出结论，所以无法判定。看一眼 pr.md 和改动，确认后再开 PR，或者重新验证一次。')
  return t('证据还不够下结论，所以无法判定。看一眼 pr.md 里写的证据缺口，补充 Issue 后重新验证，') + look
}
