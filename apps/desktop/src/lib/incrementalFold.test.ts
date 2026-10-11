import { describe, expect, it } from 'vitest'
import { IncrementalFold } from './incrementalFold'

type E = { seq: number; v: number }
const sum = (s: number[], e: E) => [...s, e.v]
const ev = (n: number, from = 0): E[] => Array.from({ length: n }, (_, i) => ({ seq: from + i, v: from + i }))

describe('IncrementalFold', () => {
  it('只折叠追加的尾部，结果与全量一致', () => {
    let calls = 0
    const f = new IncrementalFold<E, number[]>((s, e) => (calls++, sum(s, e)), [])
    const a = ev(5)
    expect(f.fold(a)).toEqual([0, 1, 2, 3, 4])
    const b = [...a, ...ev(3, 5)]
    calls = 0
    expect(f.fold(b)).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
    expect(calls).toBe(3)
  })
  it('数组被替换 / 乱序插入时从头折叠', () => {
    const f = new IncrementalFold<E, number[]>(sum, [])
    f.fold(ev(4))
    expect(f.fold(ev(2, 10))).toEqual([10, 11])
    const base = ev(3)
    f.fold(base)
    const reordered = [base[0], { seq: 1, v: 99 }, ...base.slice(1)]
    expect(f.fold(reordered)).toEqual([0, 99, 1, 2])
  })
  it('upto 前进增量、后退重算', () => {
    const f = new IncrementalFold<E, number[]>(sum, [])
    const a = ev(6)
    expect(f.fold(a, 2)).toEqual([0, 1, 2])
    expect(f.fold(a, 4)).toEqual([0, 1, 2, 3, 4])
    expect(f.fold(a, 1)).toEqual([0, 1])
    expect(f.fold(a)).toEqual([0, 1, 2, 3, 4, 5])
  })
})
