/* eslint-disable */
// 由 scripts/gen-event-types.mjs 从 schemas/tw-events-1.schema.json 生成，勿手改。
// 重新生成：npm run gen:events

/**
 * TriWitness 轨迹事件（一行一个 JSON 对象）。读取方遇到未知 kind 必须忽略。
 */
export type TwEvents1 =
  | TaskStartedEvent
  | StateChangeEvent
  | ModelCallEvent
  | ToolCallEvent
  | CheckpointEvent
  | LoopWarningEvent
  | HitlRequestEvent
  | HitlResponseEvent
  | ApprovalRequestedEvent
  | ApprovalResolvedEvent
  | ModeChangedEvent
  | VerificationEvent
  | ReviewEvent
  | TaskFinishedEvent
  | ErrorEvent
export type Kind = 'task_started'
export type ConfigHash = string
export type Display = string | null
export type IssueNumber = number | null
export type IssueTitle = string
export type Mode = 'background' | 'interactive' | 'eval'
export type Repo = string
export type RoleHint = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Role = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId = string
export type Seq = number
export type SpanId = string | null
export type TaskId = string
export type TraceId = string | null
export type Ts = string
export type V = 1
export type Kind1 = 'state_change'
export type Display1 = string | null
export type TaskState =
  | 'received'
  | 'preparing'
  | 'planning'
  | 'await_plan_approval'
  | 'reproducing'
  | 'executing'
  | 'verifying'
  | 'reviewing'
  | 'packaging'
  | 'await_pr_approval'
  | 'pr_opened'
  | 'ci_watch'
  | 'done'
  | 'needs_human'
  | 'budget_exceeded'
  | 'failed'
  | 'cancelled'
export type RoleHint1 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Role1 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId1 = string
export type Seq1 = number
export type SpanId1 = string | null
export type TaskId1 = string
export type TraceId1 = string | null
export type Ts1 = string
export type V1 = 1
export type Kind2 = 'model_call'
export type CostCny = number
export type Display2 = string | null
export type FinishReason = string | null
export type LatencyMs = number
export type Model = string
export type Peak = boolean | null
export type RoleHint2 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type ServedModel = string | null
export type Thinking = boolean
export type CacheHitTokens = number
export type CacheMissTokens = number
export type InputTokens = number
export type OutputTokens = number
export type ReasoningTokens = number | null
export type Role2 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId2 = string
export type Seq2 = number
export type SpanId2 = string | null
export type TaskId2 = string
export type TraceId2 = string | null
export type Ts2 = string
export type V2 = 1
export type Kind3 = 'tool_call'
export type Display3 = string | null
export type DurationMs = number
export type ErrorType = string | null
export type ExitCode = number | null
export type Ok = boolean
export type OutputRef = string | null
export type Permission = ('allow' | 'ask' | 'deny') | null
export type PermissionRule = string | null
export type RoleHint3 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Tool = string
export type Truncated = boolean
export type Role3 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId3 = string
export type Seq3 = number
export type SpanId3 = string | null
export type TaskId3 = string
export type TraceId3 = string | null
export type Ts3 = string
export type V3 = 1
export type Kind4 = 'checkpoint'
export type Display4 = string | null
export type Label = string
export type Ref = string | null
export type RoleHint4 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Role4 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId4 = string
export type Seq4 = number
export type SpanId4 = string | null
export type TaskId4 = string
export type TraceId4 = string | null
export type Ts4 = string
export type V4 = 1
export type Kind5 = 'loop_warning'
export type Detail = string | null
export type Display5 = string | null
export type Level = number
export type RoleHint5 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Signal = 'repeat_action' | 'consecutive_failures' | 'no_progress'
export type Role5 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId5 = string
export type Seq5 = number
export type SpanId5 = string | null
export type TaskId5 = string
export type TraceId5 = string | null
export type Ts5 = string
export type V5 = 1
export type Kind6 = 'hitl_request'
export type Blocking = boolean
export type Display6 = string | null
export type Options = string[]
export type Question = string
export type RequestId = string
export type RoleHint6 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Role6 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId6 = string
export type Seq6 = number
export type SpanId6 = string | null
export type TaskId6 = string
export type TraceId6 = string | null
export type Ts6 = string
export type V6 = 1
export type Kind7 = 'hitl_response'
export type Answer = string
export type By = string
export type Display7 = string | null
export type RequestId1 = string
export type RoleHint7 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Role7 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId7 = string
export type Seq7 = number
export type SpanId7 = string | null
export type TaskId7 = string
export type TraceId7 = string | null
export type Ts7 = string
export type V7 = 1
export type Kind8 = 'approval_requested'
export type Action = string
export type Backend = 'none' | 'docker' | 'wsl2' | 'remote'
export type Display8 = string | null
export type Options1 = ('allow_once' | 'allow_session' | 'allow_always' | 'deny')[]
export type Reason = string
export type RequestId2 = string
export type Risk = 'L0' | 'L1' | 'L2' | 'L3'
export type RoleHint8 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Rule = string | null
export type RuleSource = ('default' | 'user' | 'project' | 'local' | 'session' | 'managed') | null
export type SuggestedRule = string | null
export type TimeoutS = number | null
export type Tool1 = string
export type Role8 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId8 = string
export type Seq8 = number
export type SpanId8 = string | null
export type TaskId8 = string
export type TraceId8 = string | null
export type Ts8 = string
export type V8 = 1
export type Kind9 = 'approval_resolved'
export type By1 = 'user' | 'policy' | 'timeout' | 'cancelled'
export type Comment = string | null
export type Decision = 'allow' | 'deny'
export type Display9 = string | null
export type RequestId3 = string
export type RoleHint9 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type SavedRule = string | null
export type Scope = 'once' | 'session' | 'always'
export type Role9 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId9 = string
export type Seq9 = number
export type SpanId9 = string | null
export type TaskId9 = string
export type TraceId9 = string | null
export type Ts9 = string
export type V9 = 1
export type Kind10 = 'mode_changed'
export type Backend1 = 'none' | 'docker' | 'wsl2' | 'remote'
export type By2 = 'user' | 'system' | 'auto_revert'
export type Display10 = string | null
export type FromMode = 'plan' | 'ask' | 'auto_edit' | 'auto' | 'full_access' | 'unrestricted'
export type Reason1 = string | null
export type Risk1 = 'normal' | 'high'
export type RoleHint10 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Scope1 = 'task' | 'session'
export type ToMode = 'plan' | 'ask' | 'auto_edit' | 'auto' | 'full_access' | 'unrestricted'
export type Role10 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId10 = string
export type Seq10 = number
export type SpanId10 = string | null
export type TaskId10 = string
export type TraceId10 = string | null
export type Ts10 = string
export type V10 = 1
export type Kind11 = 'verification'
export type CleanEnv = ('verified' | 'failed' | 'unverified') | null
export type Display11 = string | null
export type EvidenceRef = string | null
export type RiskLevel = ('L0' | 'L1' | 'L2' | 'L3') | null
export type RoleHint11 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type TestsPassed = boolean | null
export type UnverifiedReason = ('no_sandbox' | 'backend_unavailable' | 'skipped') | null
export type Verdict = 'pass' | 'fail' | 'inconclusive'
export type Role11 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId11 = string
export type Seq11 = number
export type SpanId11 = string | null
export type TaskId11 = string
export type TraceId11 = string | null
export type Ts11 = string
export type V11 = 1
export type Kind12 = 'review'
export type Display12 = string | null
export type File = string | null
export type Line = number | null
export type Message = string
export type Severity = 'blocker' | 'major' | 'minor' | 'nit'
export type Status = 'open' | 'fixed' | 'wontfix'
export type Suggestion = string | null
export type Findings = Finding[]
export type Model1 = string
export type RoleHint12 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Variant = string
export type VendorPolicy = 'single_vendor' | 'cross_vendor'
export type Role12 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId12 = string
export type Seq12 = number
export type SpanId12 = string | null
export type TaskId12 = string
export type TraceId12 = string | null
export type Ts12 = string
export type V12 = 1
export type Kind13 = 'task_finished'
export type BudgetCny = number
export type CacheHitRate = number
export type Estimated = boolean
export type Calls = number
export type CostCny1 = number
export type Model2 = string
export type PeakCalls = number
export type Role13 = 'planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier'
export type Vendor = 'deepseek' | 'qwen' | 'zhipu'
export type Lines = CostLine[]
export type PricingVersion = string
export type SandboxCostCny = number
export type TaskId13 = string
export type TotalCny = number
export type Display13 = string | null
export type Kind14 = 'added' | 'modified' | 'deleted'
export type Note = string
export type Path = string
export type Changes = FileChange[]
export type Confidence = number
export type OpenRisks = string[]
export type Cmd = string
export type Path1 = string
export type Summary = string
export type TestsPassed1 = boolean
export type TestsRun = string[]
export type RoleHint13 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Status1 = 'done' | 'failed' | 'budget_exceeded' | 'stuck' | 'needs_human' | 'cancelled'
export type Role14 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId13 = string
export type Seq13 = number
export type SpanId13 = string | null
export type TaskId14 = string
export type TraceId13 = string | null
export type Ts13 = string
export type V13 = 1
export type Kind15 = 'error'
export type Display14 = string | null
export type Message1 = string
export type RoleHint14 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'system') | null
export type Type = string
export type Role15 = ('planner' | 'executor' | 'verifier' | 'reviewer' | 'summarizer' | 'classifier') | null
export type RunId14 = string
export type Seq14 = number
export type SpanId14 = string | null
export type TaskId15 = string
export type TraceId14 = string | null
export type Ts14 = string
export type V14 = 1

export interface TaskStartedEvent {
  kind: Kind
  payload: TaskStartedPayload
  role?: Role
  run_id: RunId
  seq: Seq
  span_id?: SpanId
  task_id: TaskId
  trace_id?: TraceId
  ts: Ts
  v?: V
}
export interface TaskStartedPayload {
  config_hash: ConfigHash
  display?: Display
  issue_number?: IssueNumber
  issue_title: IssueTitle
  mode?: Mode
  repo: Repo
  role_hint?: RoleHint
  [k: string]: unknown
}
export interface StateChangeEvent {
  kind: Kind1
  payload: StateChangePayload
  role?: Role1
  run_id: RunId1
  seq: Seq1
  span_id?: SpanId1
  task_id: TaskId1
  trace_id?: TraceId1
  ts: Ts1
  v?: V1
}
export interface StateChangePayload {
  display?: Display1
  from: TaskState
  role_hint?: RoleHint1
  to: TaskState
  [k: string]: unknown
}
export interface ModelCallEvent {
  kind: Kind2
  payload: ModelCallPayload
  role?: Role2
  run_id: RunId2
  seq: Seq2
  span_id?: SpanId2
  task_id: TaskId2
  trace_id?: TraceId2
  ts: Ts2
  v?: V2
}
export interface ModelCallPayload {
  cost_cny: CostCny
  display?: Display2
  finish_reason?: FinishReason
  latency_ms: LatencyMs
  model: Model
  peak?: Peak
  role_hint?: RoleHint2
  served_model?: ServedModel
  thinking: Thinking
  usage: Usage
  [k: string]: unknown
}
export interface Usage {
  cache_hit_tokens?: CacheHitTokens
  cache_miss_tokens?: CacheMissTokens
  input_tokens?: InputTokens
  output_tokens?: OutputTokens
  reasoning_tokens?: ReasoningTokens
}
export interface ToolCallEvent {
  kind: Kind3
  payload: ToolCallPayload
  role?: Role3
  run_id: RunId3
  seq: Seq3
  span_id?: SpanId3
  task_id: TaskId3
  trace_id?: TraceId3
  ts: Ts3
  v?: V3
}
export interface ToolCallPayload {
  display?: Display3
  duration_ms: DurationMs
  error_type?: ErrorType
  exit_code?: ExitCode
  ok: Ok
  output_ref?: OutputRef
  permission?: Permission
  permission_rule?: PermissionRule
  role_hint?: RoleHint3
  tool: Tool
  truncated?: Truncated
  [k: string]: unknown
}
export interface CheckpointEvent {
  kind: Kind4
  payload: CheckpointPayload
  role?: Role4
  run_id: RunId4
  seq: Seq4
  span_id?: SpanId4
  task_id: TaskId4
  trace_id?: TraceId4
  ts: Ts4
  v?: V4
}
export interface CheckpointPayload {
  display?: Display4
  label: Label
  ref?: Ref
  role_hint?: RoleHint4
  [k: string]: unknown
}
export interface LoopWarningEvent {
  kind: Kind5
  payload: LoopWarningPayload
  role?: Role5
  run_id: RunId5
  seq: Seq5
  span_id?: SpanId5
  task_id: TaskId5
  trace_id?: TraceId5
  ts: Ts5
  v?: V5
}
export interface LoopWarningPayload {
  detail?: Detail
  display?: Display5
  level: Level
  role_hint?: RoleHint5
  signal: Signal
  [k: string]: unknown
}
export interface HitlRequestEvent {
  kind: Kind6
  payload: HitlRequestPayload
  role?: Role6
  run_id: RunId6
  seq: Seq6
  span_id?: SpanId6
  task_id: TaskId6
  trace_id?: TraceId6
  ts: Ts6
  v?: V6
}
export interface HitlRequestPayload {
  blocking?: Blocking
  display?: Display6
  options: Options
  question: Question
  request_id: RequestId
  role_hint?: RoleHint6
  [k: string]: unknown
}
export interface HitlResponseEvent {
  kind: Kind7
  payload: HitlResponsePayload
  role?: Role7
  run_id: RunId7
  seq: Seq7
  span_id?: SpanId7
  task_id: TaskId7
  trace_id?: TraceId7
  ts: Ts7
  v?: V7
}
export interface HitlResponsePayload {
  answer: Answer
  by: By
  display?: Display7
  request_id: RequestId1
  role_hint?: RoleHint7
  [k: string]: unknown
}
export interface ApprovalRequestedEvent {
  kind: Kind8
  payload: ApprovalRequestedPayload
  role?: Role8
  run_id: RunId8
  seq: Seq8
  span_id?: SpanId8
  task_id: TaskId8
  trace_id?: TraceId8
  ts: Ts8
  v?: V8
}
/**
 * 权限引擎判为 ask 时发出（spec 006 §7、ADR-0005）。
 *
 * eval / 非交互模式不发此事件，直接写 approval_resolved(by=policy)。
 */
export interface ApprovalRequestedPayload {
  action: Action
  backend?: Backend
  display?: Display8
  options?: Options1
  reason: Reason
  request_id: RequestId2
  risk?: Risk
  role_hint?: RoleHint8
  rule?: Rule
  rule_source?: RuleSource
  suggested_rule?: SuggestedRule
  timeout_s?: TimeoutS
  tool: Tool1
  [k: string]: unknown
}
export interface ApprovalResolvedEvent {
  kind: Kind9
  payload: ApprovalResolvedPayload
  role?: Role9
  run_id: RunId9
  seq: Seq9
  span_id?: SpanId9
  task_id: TaskId9
  trace_id?: TraceId9
  ts: Ts9
  v?: V9
}
export interface ApprovalResolvedPayload {
  by: By1
  comment?: Comment
  decision: Decision
  display?: Display9
  request_id: RequestId3
  role_hint?: RoleHint9
  saved_rule?: SavedRule
  scope?: Scope
  [k: string]: unknown
}
export interface ModeChangedEvent {
  kind: Kind10
  payload: ModeChangedPayload
  role?: Role10
  run_id: RunId10
  seq: Seq10
  span_id?: SpanId10
  task_id: TaskId10
  trace_id?: TraceId10
  ts: Ts10
  v?: V10
}
/**
 * 审批模式切换（spec 006 §4.6）。risk=high（full_access / unrestricted）时 UI 显示常驻红色横幅，直到切回。
 */
export interface ModeChangedPayload {
  backend?: Backend1
  by?: By2
  display?: Display10
  from_mode: FromMode
  reason?: Reason1
  risk?: Risk1
  role_hint?: RoleHint10
  scope?: Scope1
  to_mode: ToMode
  [k: string]: unknown
}
export interface VerificationEvent {
  kind: Kind11
  payload: VerificationPayload
  role?: Role11
  run_id: RunId11
  seq: Seq11
  span_id?: SpanId11
  task_id: TaskId11
  trace_id?: TraceId11
  ts: Ts11
  v?: V11
}
export interface VerificationPayload {
  clean_env?: CleanEnv
  display?: Display11
  evidence_ref?: EvidenceRef
  risk_level?: RiskLevel
  role_hint?: RoleHint11
  tests_passed?: TestsPassed
  unverified_reason?: UnverifiedReason
  verdict: Verdict
  [k: string]: unknown
}
export interface ReviewEvent {
  kind: Kind12
  payload: ReviewPayload
  role?: Role12
  run_id: RunId12
  seq: Seq12
  span_id?: SpanId12
  task_id: TaskId12
  trace_id?: TraceId12
  ts: Ts12
  v?: V12
}
export interface ReviewPayload {
  display?: Display12
  findings?: Findings
  model: Model1
  role_hint?: RoleHint12
  variant: Variant
  vendor_policy?: VendorPolicy
  [k: string]: unknown
}
export interface Finding {
  file?: File
  line?: Line
  message: Message
  severity: Severity
  status?: Status
  suggestion?: Suggestion
}
export interface TaskFinishedEvent {
  kind: Kind13
  payload: TaskFinishedPayload
  role?: Role14
  run_id: RunId13
  seq: Seq13
  span_id?: SpanId13
  task_id: TaskId14
  trace_id?: TraceId13
  ts: Ts13
  v?: V13
}
export interface TaskFinishedPayload {
  cost_report?: CostReport | null
  display?: Display13
  finish_report?: FinishReport | null
  role_hint?: RoleHint13
  status: Status1
  [k: string]: unknown
}
export interface CostReport {
  budget_cny: BudgetCny
  cache_hit_rate: CacheHitRate
  estimated?: Estimated
  lines: Lines
  pricing_version: PricingVersion
  sandbox_cost_cny?: SandboxCostCny
  task_id: TaskId13
  total_cny: TotalCny
}
export interface CostLine {
  calls: Calls
  cost_cny: CostCny1
  model: Model2
  peak_calls?: PeakCalls
  role: Role13
  usage: Usage
  vendor: Vendor
}
export interface FinishReport {
  changes: Changes
  confidence: Confidence
  open_risks?: OpenRisks
  repro?: ReproRef | null
  summary: Summary
  tests_passed: TestsPassed1
  tests_run?: TestsRun
}
export interface FileChange {
  kind: Kind14
  note?: Note
  path: Path
}
export interface ReproRef {
  cmd: Cmd
  path: Path1
}
export interface ErrorEvent {
  kind: Kind15
  payload: ErrorPayload
  role?: Role15
  run_id: RunId14
  seq: Seq14
  span_id?: SpanId14
  task_id: TaskId15
  trace_id?: TraceId14
  ts: Ts14
  v?: V14
}
export interface ErrorPayload {
  display?: Display14
  message: Message1
  role_hint?: RoleHint14
  type: Type
  [k: string]: unknown
}
