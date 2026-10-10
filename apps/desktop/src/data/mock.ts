import type { ActivitySession, ChatMessage, Conversation } from '../types'

export const conversations: Conversation[] = [
  {
    id: 'c1',
    title: '修复登录态刷新竞态',
    preview: '三证：复现 → 补测 → 干净沙箱复验',
    updatedAt: '刚才',
    project: 'triwitness/core',
    active: true,
  },
  {
    id: 'c2',
    title: 'Issue #128 · 缓存键冲突',
    preview: 'Reviewer 指出边界条件未覆盖',
    updatedAt: '昨晚',
    project: 'triwitness/core',
  },
  {
    id: 'c3',
    title: '评测集 warm-up 跑通',
    preview: 'dev suite · 3 tasks · 空闲窗口',
    updatedAt: '周三',
    project: 'evals',
  },
  {
    id: 'c4',
    title: '证据包 schema 对齐',
    preview: 'risk L0–L3 字段定稿',
    updatedAt: '周一',
    project: 'triwitness/evidence',
  },
]

export const messages: ChatMessage[] = [
  {
    id: 'm1',
    role: 'user',
    content:
      '帮我处理 GitHub Issue #87：用户在并发刷新 token 时偶发 401。希望走完整三证流程——先复现、再修、最后干净沙箱复验，并让 reviewer 过一遍。',
    timestamp: '04:12',
  },
  {
    id: 'm2',
    role: 'assistant',
    content:
      '好。我会按 TriWitness 的标准编排推进：\n\n1. **Planner** 拆解复现路径与验收条件\n2. **Executor** 在隔离沙箱里改代码\n3. **Verifier** 用干净沙箱重跑测试\n4. **Reviewer**（DeepSeek Flash 思考模式）交叉审阅',
    meta: 'deepseek-flash · 空闲价',
    timestamp: '04:12',
  },
  {
    id: 'm3',
    role: 'assistant',
    content:
      '复现已确认：两个并发 `/auth/refresh` 会共用同一把旧 refresh token，第二把请求把会话作废。正在写入失败用例并准备修复。',
    meta: 'verifier · 干净沙箱',
    timestamp: '04:18',
  },
]

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
