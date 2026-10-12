import { describe, expect, it } from 'vitest'
import { parseMemory, shortSource } from './memory'

describe('parseMemory', () => {
  it('缺省 / null / 非对象 / 空 → null（不显示芯片）', () => {
    expect(parseMemory(undefined)).toBeNull()
    expect(parseMemory(null)).toBeNull()
    expect(parseMemory('x')).toBeNull()
    expect(parseMemory([])).toBeNull()
    expect(parseMemory({ facts: [], skills: [] })).toBeNull()
  })

  it('解析事实与技能，忽略坏条目', () => {
    const m = parseMemory({
      repo_key: 'github.com_o_r',
      facts: [{ id: 'f1', text: '测试用 uv run pytest -q', kind: 'test_cmd', source: 'tw://run/r_01ABCDEFGHJK' }, { id: 'bad' }, 3],
      skills: [{ name: 'fix-ci', version: 2, description: '修 CI', source: null }, { version: 1 }],
      facts_total: 5,
      skills_total: 1,
      episodes: true,
    })
    expect(m).not.toBeNull()
    expect(m!.facts).toEqual([{ id: 'f1', text: '测试用 uv run pytest -q', kind: 'test_cmd', source: 'tw://run/r_01ABCDEFGHJK' }])
    expect(m!.skills).toEqual([{ name: 'fix-ci', version: 2, description: '修 CI', source: null }])
    expect(m!.factsTotal).toBe(5)
    expect(m!.episodes).toBe(true)
  })

  it('只有总数（摘要被截断）也显示', () => {
    expect(parseMemory({ facts_total: 3 })?.factsTotal).toBe(3)
  })
})

describe('shortSource', () => {
  it('缩短 tw://run 来源', () => {
    expect(shortSource('tw://run/r_01M4KEZZXH9M1VAEDJ7A4Y6MGR')).toBe('r_0…4Y6MGR')
    expect(shortSource('tw://run/r_1')).toBe('r_1')
    expect(shortSource('manual')).toBe('manual')
    expect(shortSource(null)).toBeNull()
  })
})
