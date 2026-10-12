import type { Phase } from '../data/mapEvent'

const TERMINAL: ReadonlySet<Phase> = new Set(['done', 'failed', 'budget', 'cancelled', 'waiting'])

/**
 * 顶部状态签与右栏书写同步（批次 2-3）：终态（完成 / 未过 / 触及安全上限 / 已停止 …）只在右栏
 * 已经写出最后一个事件之后才显示；之前沿用「已写出部分」折叠出来的状态。右栏不在（作品栏打开）时不等。
 */
export function syncTerminal<T extends { phase: Phase; label: string; lastSeq: number }>(
  live: T,
  revealed: { phase: Phase; label: string },
  revealedSeq: number,
  streamShown: boolean,
): T {
  if (!streamShown || !TERMINAL.has(live.phase) || revealedSeq >= live.lastSeq) return live
  const phase = TERMINAL.has(revealed.phase) ? 'active' : revealed.phase
  return { ...live, phase: phase === 'idle' ? 'active' : phase, label: revealed.label }
}
