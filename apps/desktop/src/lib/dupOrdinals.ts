/**
 * 侧栏同名会话序号（·1 ·2 ·3）：按会话第一轮开始时间（firstAt，即根任务时间）升序编号，
 * 稳定——后续活动只改 at，不改 firstAt，所以不会重新编号。缺 firstAt 时按 id 排，保证确定。
 */
export function dupOrdinals(items: readonly { id: string; title: string; firstAt?: number }[]): Map<string, number> {
  const byTitle = new Map<string, { id: string; firstAt?: number }[]>()
  for (const c of items) byTitle.set(c.title, [...(byTitle.get(c.title) ?? []), c])
  const out = new Map<string, number>()
  for (const list of byTitle.values()) {
    if (list.length < 2) continue
    const sorted = [...list].sort(
      (a, b) => (a.firstAt ?? Infinity) - (b.firstAt ?? Infinity) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
    )
    sorted.forEach((c, i) => out.set(c.id, i + 1))
  }
  return out
}
