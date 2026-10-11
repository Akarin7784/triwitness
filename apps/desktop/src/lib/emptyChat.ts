/**
 * 新会话复用（BUG3）：连点“新会话”不再堆出一串空会话。
 * 空 = 还没起任务（local:）、没有消息、草稿为空，且项目归属与要新建的一致。返回最新的那个。
 */
export function findEmptyChat<K extends string>(
  locals: { id: K }[],
  o: { messages: Record<string, unknown[] | undefined>; draft: (id: string) => string; project: (id: string) => string | null; want: string | null },
): K | null {
  for (const l of locals) {
    if (!l.id.startsWith('local:')) continue
    if ((o.messages[l.id]?.length ?? 0) > 0) continue
    if (o.draft(l.id).trim()) continue
    if (o.project(l.id) !== o.want) continue
    return l.id
  }
  return null
}
