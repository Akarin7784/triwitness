import type { Phase } from '../data/mapEvent'

const TERMINAL: ReadonlySet<Phase> = new Set(['done', 'failed', 'budget', 'cancelled', 'waiting'])

/**
 * 顶部状态签与书写同步（批次 2-3，阿验 b2-r1 P1）：终态（完成 / 未过 / 触及安全上限 / 已停止 …）
 * 只在右栏把最后一个事件（收尾行「系统 … · ¥…」，对话里的结论随同一事件出现）**完整写完**之后才显示。
 * 在此之前——包括终态章节分隔线已写出、收尾行还在写——显示「进行中」。右栏不在（作品栏打开）时不等。
 */
export function syncTerminal<T extends { phase: Phase; label: string; lastSeq: number }>(
  live: T,
  stream: { revealedSeq: number; done: boolean; shown: boolean },
  pendingLabel: string,
  /** 收尾事件（task_finished / turn_finished）的 seq；还没到时为 -1——终态分隔线（state_change）先到也不翻 */
  finishedSeq: number,
): T {
  if (!stream.shown || !TERMINAL.has(live.phase)) return live
  if (finishedSeq >= 0 && stream.done && stream.revealedSeq >= Math.max(finishedSeq, live.lastSeq)) return live
  return { ...live, phase: 'active', label: pendingLabel }
}

/** 事件里收尾事件的 seq（没有则 -1） */
export function finishedSeqOf(events: readonly { kind: string; seq: number }[]): number {
  for (let i = events.length - 1; i >= 0; i--) {
    const k = events[i].kind
    if (k === 'task_finished' || k === 'turn_finished') return events[i].seq
  }
  return -1
}
