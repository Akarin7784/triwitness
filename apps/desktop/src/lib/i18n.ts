/**
 * 界面语言（UI-21 第 3 轮）：中文即键，英文查表。启动时定一次语言，切换语言重载窗口——
 * 所以模块顶层的常量也能直接用 t()。直接读 localStorage，不引 prefs.ts（避免循环依赖）。
 * 写给模型的提示词、导出给人看的对话原文、确认短语“我了解风险”不翻译。
 */
import { EN } from './i18n.en'

export type Lang = 'zh' | 'en'

function readLang(): Lang {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem('tw.prefs')
    return raw && (JSON.parse(raw) as { language?: string }).language === 'en' ? 'en' : 'zh'
  } catch {
    return 'zh'
  }
}

let lang: Lang = readLang()

export function currentLang(): Lang {
  return lang
}

/** 仅测试用 */
export function setLangForTest(l: Lang) {
  lang = l
}

/** t('已写入{0}', x)：中文原文为键；英文缺词时回落中文。 */
export function t(zh: string, ...args: (string | number)[]): string {
  const s = lang === 'en' ? (EN[zh] ?? zh) : zh
  return args.length ? s.replace(/\{(\d+)\}/g, (m: string, i: string) => (Number(i) < args.length ? String(args[Number(i)]) : m)) : s
}

if (typeof document !== 'undefined') document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN'

/** 日期 / 数字格式用的区域 */
export function locale(): string {
  return lang === 'en' ? 'en-US' : 'zh-CN'
}
