import { execFileSync } from 'node:child_process'
import { readdirSync, readFileSync } from 'node:fs'
import { afterEach, describe, expect, it } from 'vitest'
import { EN } from './i18n.en'
import { locale, setLangForTest, t } from './i18n'

const CJK = /[\u3400-\u9fff\u3000-\u303f\uff01-\uff5e]/
const holes = (s: string) => [...s.matchAll(/\{(\d+)\}/g)].map((m) => m[1]).sort().join(',')

function sourceKeys(): string[] {
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(`${dir}/${e.name}`) : /\.tsx?$/.test(e.name) ? [`${dir}/${e.name}`] : []))
  const files = walk('src')
  const keys = new Set<string>()
  for (const f of files.filter((x) => !/\.test\.|i18n/.test(x))) {
    for (const m of readFileSync(f, 'utf8').matchAll(/\btr?\(\s*'((?:[^'\\]|\\.)*)'/g)) {
      if (CJK.test(m[1])) keys.add(m[1].replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\\\/g, '\\'))
    }
  }
  return [...keys]
}

describe('i18n', () => {
  afterEach(() => setLangForTest('zh'))

  it('中文是键，默认原样返回并填参数', () => {
    expect(t('已下载 {0}', 'a.md')).toBe('已下载 a.md')
    expect(locale()).toBe('zh-CN')
  })

  it('英文查表，缺词回落中文', () => {
    setLangForTest('en')
    expect(t('已下载 {0}', 'a.md')).toBe('Downloaded a.md')
    expect(t('版本 {0}/{1}', 2, 3)).toBe('Version 2/3')
    expect(t('不存在的词')).toBe('不存在的词')
    expect(locale()).toBe('en-US')
  })

  it('确认短语不翻译', () => {
    expect(EN['我了解风险']).toBeUndefined()
  })

  it('源码里每个 t() 键都有英文，占位符一致', () => {
    const keys = sourceKeys()
    expect(keys.length).toBeGreaterThan(300)
    expect(keys.filter((k) => !(k in EN))).toEqual([])
    expect(keys.filter((k) => holes(k) !== holes(EN[k]))).toEqual([])
    expect(Object.values(EN).filter((v) => /[\u3400-\u9fff]/.test(v) && v !== '简体中文')).toEqual([])
  })

  it('界面里没有漏包的中文字面量', () => {
    expect(() => execFileSync('node', ['tools/i18n-wrap.mjs', '--check'], { stdio: 'pipe' })).not.toThrow()
  }, 20_000)
})
