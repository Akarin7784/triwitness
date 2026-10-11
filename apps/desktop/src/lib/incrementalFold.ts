/**
 * 增量折叠（perf）：事件列表通常只在尾部追加，没必要每帧从头 reduce。
 * 记住上次折叠到的数组与位置；新数组若是旧数组的延长（首元素与上次最后折叠的元素都是同一对象），
 * 只折叠新增部分；否则（重置 / 乱序插入 / upto 回退）从头来。结果与一次性全量折叠完全一致。
 */
export class IncrementalFold<E extends { seq: number }, S> {
  private events: readonly E[] = []
  private idx = 0
  private upto = Number.POSITIVE_INFINITY
  private state: S
  private readonly reduce: (s: S, e: E) => S
  private readonly init: S

  constructor(reduce: (s: S, e: E) => S, init: S) {
    this.reduce = reduce
    this.init = init
    this.state = init
  }

  fold(events: readonly E[], upto = Number.POSITIVE_INFINITY): S {
    const extends_ =
      this.idx <= events.length &&
      upto >= this.upto &&
      (this.idx === 0 || (events[0] === this.events[0] && events[this.idx - 1] === this.events[this.idx - 1]))
    if (!extends_) {
      this.idx = 0
      this.state = this.init
    }
    let s = this.state
    let i = this.idx
    while (i < events.length && events[i].seq <= upto) s = this.reduce(s, events[i++])
    this.events = events
    this.idx = i
    this.upto = upto
    this.state = s
    return s
  }
}
