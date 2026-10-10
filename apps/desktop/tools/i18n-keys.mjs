// 列出源码里 t('…') / tr('…') 的全部中文键（i18n.test 用同一规则检查英文表覆盖）
import { readFileSync, readdirSync } from 'node:fs'
function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(`${dir}/${e.name}`) : /\.tsx?$/.test(e.name) ? [`${dir}/${e.name}`] : []))
}
const files = walk('src').filter((f) => !/\.test\.|i18n/.test(f))
const keys = new Set()
const re = /\btr?\(\s*'((?:[^'\\]|\\.)*)'/g
for (const f of files) for (const m of readFileSync(f, 'utf8').matchAll(re)) if (/[\u3400-\u9fff\u3000-\u303f\uff01-\uff5e]/.test(m[1])) keys.add(m[1].replace(/\\'/g, "'").replace(/\\n/g, '\n').replace(/\\\\/g, '\\'))
console.log(JSON.stringify([...keys].sort(), null, 0).replace(/","/g, '",\n"'))
