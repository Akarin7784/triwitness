import type { ActivitySession } from '../types'

export const demoSession: ActivitySession = {
  id: 's1',
  title: 'Issue #87',
  subtitle: 'plan → execute → verify → review',
  lines: [
    {
      id: 'l1',
      role: 'system',
      text: 'triwitness@sandbox:~$ tw run --issue 87 --roles planner,executor,verifier,reviewer',
      pauseBefore: 200,
    },
    {
      id: 'l2',
      role: 'system',
      text: '预算闸门 · 空闲窗口 · 单任务上限 ¥0.80 · 缓存命中优先',
      pauseBefore: 400,
    },
    {
      id: 'l3',
      role: 'planner',
      text: '阅读 Issue #87：并发 refresh 导致 401。验收：双请求并行时会话仍有效；补回归测试。',
      pauseBefore: 600,
    },
    {
      id: 'l4',
      role: 'planner',
      text: '步骤：定位 AuthService.refresh → 写失败复现 → 加锁/轮转策略 → 干净沙箱复验。',
      pauseBefore: 350,
    },
    {
      id: 'l5',
      role: 'executor',
      text: '$ git checkout -b tw/issue-87-refresh-race',
      pauseBefore: 500,
    },
    {
      id: 'l6',
      role: 'executor',
      text: '打开 src/auth/service.py · 发现 refresh 未串行化，两处同时写 session store。',
      pauseBefore: 450,
    },
    {
      id: 'l7',
      role: 'executor',
      text: '写入 tests/test_auth_refresh_race.py —— 预期失败（红灯）。',
      pauseBefore: 400,
    },
    {
      id: 'l8',
      role: 'executor',
      text: 'pytest … FAILED  test_concurrent_refresh_keeps_session',
      pauseBefore: 380,
    },
    {
      id: 'l9',
      role: 'executor',
      text: '应用修复：asyncio.Lock + 单次轮转；旧 token 标记已消费。',
      pauseBefore: 420,
    },
    {
      id: 'l10',
      role: 'verifier',
      text: 'fork 干净沙箱快照 · 安装依赖缓存命中 · 重跑全量 auth 套件',
      pauseBefore: 550,
    },
    {
      id: 'l11',
      role: 'verifier',
      text: '12 passed · 0 failed · 反作弊：测试未被改写 · 证据包已归档',
      pauseBefore: 400,
    },
    {
      id: 'l12',
      role: 'reviewer',
      text: 'deepseek-flash · thinking · 关注锁粒度与死锁风险、日志是否泄露 token',
      pauseBefore: 600,
    },
    {
      id: 'l13',
      role: 'reviewer',
      text: 'L1 风险：可接受。建议在 PR 描述写明「双飞 refresh」复现步骤。准予开 PR。',
      pauseBefore: 450,
    },
    {
      id: 'l14',
      role: 'system',
      text: '✓ 证据包 ready · cost ¥0.19 · cache hit 94% · 准备 gh pr create',
      pauseBefore: 500,
    },
  ],
}

export const roleLabel: Record<string, string> = {
  planner: '规划',
  executor: '执行',
  verifier: '验证',
  reviewer: '评审',
  system: '系统',
  user: '你',
}

export const roleColor: Record<string, string> = {
  planner: 'var(--color-amber)',
  executor: 'var(--color-espresso)',
  verifier: 'var(--color-teal)',
  reviewer: 'var(--color-plum)',
  system: 'var(--color-sepia-muted)',
  user: 'var(--color-sage)',
}
