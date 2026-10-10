// UI-21 第 3 轮 i18n：把界面里的中文字面量包进 t()（一次性改写 + 之后可复跑检查）。
//   node tools/i18n-wrap.mjs            → 只报告
//   node tools/i18n-wrap.mjs --write    → 改写文件
//   node tools/i18n-wrap.mjs --check    → 有没包的中文就失败（i18n.test 调用）；行内写 i18n-ignore 可豁免
// 跳过：比较 / case / includes 等“数据用”的字符串（列出来人工看）、类型位置、import、确认短语。
import ts from 'typescript'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { relative, dirname } from 'node:path'

const WRITE = process.argv.includes('--write')
const CJK = /[\u3400-\u9fff\u3000-\u303f\uff01-\uff5e]/
const SKIP_FILES = [/\.test\./, /\.gen\./, /^src\/data\/mock\.ts$/, /^src\/data\/sources\/mock\.ts$/, /^src\/data\/turns\.ts$/, /^src\/lib\/guidance\.ts$/, /^src\/lib\/i18n/, /__fixtures__/]
const KEEP = new Set(['我了解风险'])
const DATA_METHODS = new Set(['includes', 'startsWith', 'endsWith', 'split', 'indexOf', 'replace', 'replaceAll', 'match', 'test'])
function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(`${dir}/${e.name}`) : /\.tsx?$/.test(e.name) ? [`${dir}/${e.name}`] : []))
}
const files = walk('src').filter((f) => !SKIP_FILES.some((r) => r.test(f)))

const quote = (s) => `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n')}'`
function cookJsx(raw) {
  const lines = raw.split(/\r?\n/)
  if (lines.length === 1) return raw
  const out = []
  lines.forEach((l, i) => {
    let s = l
    if (i > 0) s = s.replace(/^[ \t]+/, '')
    if (i < lines.length - 1) s = s.replace(/[ \t]+$/, '')
    if (s) out.push(s)
  })
  return out.join(' ')
}

let report = []
let total = 0
for (const file of files) {
  const src = readFileSync(file, 'utf8')
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  // 文件里若自己声明了 t，就用别名 tr
  let shadow = false
  const scan = (n) => {
    if ((ts.isVariableDeclaration(n) || ts.isParameter(n) || ts.isBindingElement(n)) && ts.isIdentifier(n.name) && n.name.text === 't') shadow = true
    ts.forEachChild(n, scan)
  }
  scan(sf)
  const T = shadow ? 'tr' : 't'
  let count = 0
  const line = (n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  const flag = (n, why) => report.push(`${file}:${line(n)}  [${why}]  ${n.getText(sf).slice(0, 70)}`)

  const isDataUse = (n) => {
    const p = n.parent
    if (ts.isBinaryExpression(p) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken].includes(p.operatorToken.kind)) return 'compare'
    if (ts.isCaseClause(p)) return 'case'
    if (ts.isCallExpression(p) && p.arguments.includes(n)) {
      const e = p.expression
      if (ts.isPropertyAccessExpression(e) && DATA_METHODS.has(e.name.text)) return 'data-method'
      if (ts.isPropertyAccessExpression(e) && ts.isIdentifier(e.expression) && e.expression.text === 'console') return 'console'
      if (ts.isIdentifier(e) && (e.text === 't' || e.text === 'tr')) return 'already'
    }
    if (ts.isNewExpression(p) && ts.isIdentifier(p.expression) && p.expression.text === 'RegExp') return 'regexp'
    if (ts.isLiteralTypeNode(p) || ts.isImportDeclaration(p) || ts.isExportDeclaration(p) || ts.isExternalModuleReference(p)) return 'type'
    if ((ts.isPropertyAssignment(p) || ts.isPropertySignature(p) || ts.isMethodDeclaration(p) || ts.isEnumMember(p)) && p.name === n) return 'key'
    if (ts.isElementAccessExpression(p) && p.argumentExpression === n) return 'key'
    if (ts.isJsxAttribute(p) && ['data-testid', 'className', 'key', 'id'].includes(p.name.getText(sf))) return 'attr'
    return null
  }

  /** 节点改写后的源码 */
  function rewrite(node) {
    const start = node.getStart(sf)
    let text = src.slice(start, node.getEnd())
    const edits = []
    const visit = (n) => {
      const r = replacement(n)
      if (r !== null) edits.push([n.getStart(sf), n.getEnd(), r])
      else ts.forEachChild(n, visit)
    }
    ts.forEachChild(node, visit)
    edits.sort((a, b) => b[0] - a[0])
    for (const [s, e, r] of edits) text = text.slice(0, s - start) + r + text.slice(e - start)
    return text
  }

  function templateCall(parts, exprs) {
    let key = ''
    parts.forEach((p, i) => {
      key += p
      if (i < exprs.length) key += `{${i}}`
    })
    return `${T}(${quote(key)}${exprs.map((e) => ', ' + e).join('')})`
  }

  function replacement(n) {
    if (ignored(n)) return null
    // JSX 子节点：文字 + 简单表达式 → 一句 t('… {0} …', x)
    if ((ts.isJsxElement(n) || ts.isJsxFragment(n)) && n.children.some((c) => ts.isJsxText(c) && CJK.test(c.text))) {
      const kids = n.children
      const simple = kids.every((c) => ts.isJsxText(c) || (ts.isJsxExpression(c) && c.expression && !containsJsx(c.expression)))
      const exprCount = kids.filter((c) => ts.isJsxExpression(c)).length
      if (simple && exprCount > 0 && exprCount <= 4) {
        const parts = ['']
        const exprs = []
        for (const c of kids) {
          if (ts.isJsxText(c)) parts[parts.length - 1] += cookJsx(c.text)
          else {
            exprs.push(rewrite(c.expression))
            parts.push('')
          }
        }
        const lead = parts[0].match(/^\s*/)[0]
        const tail = parts[parts.length - 1].match(/\s*$/)[0]
        parts[0] = parts[0].slice(lead.length)
        parts[parts.length - 1] = parts[parts.length - 1].slice(0, parts[parts.length - 1].length - tail.length)
        const open = ts.isJsxElement(n) ? rewrite(n.openingElement) : '<>'
        const close = ts.isJsxElement(n) ? n.closingElement.getText(sf) : '</>'
        count++
        return `${open}${lead ? ' ' : ''}{${templateCall(parts, exprs)}}${tail ? ' ' : ''}${close}`
      }
      return null
    }
    if (ts.isJsxText(n) && CJK.test(n.text)) {
      const raw = n.getText(sf)
      const lead = raw.match(/^\s*/)[0]
      const tail = raw.match(/\s*$/)[0]
      const core = cookJsx(raw.slice(lead.length, raw.length - tail.length))
      count++
      return `${lead}{${T}(${quote(core)})}${tail}`
    }
    if ((ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && CJK.test(n.text)) {
      if (KEEP.has(n.text)) return null
      const why = isDataUse(n)
      if (why) {
        if (why !== 'already' && why !== 'type' && why !== 'console') flag(n, why)
        return null
      }
      count++
      return ts.isJsxAttribute(n.parent) ? `{${T}(${quote(n.text)})}` : `${T}(${quote(n.text)})`
    }
    if (ts.isTemplateExpression(n) && hasCjkOwn(n)) {
      if (ts.isTaggedTemplateExpression(n.parent)) return null
      const why = isDataUse(n)
      if (why) {
        flag(n, why)
        return null
      }
      const parts = [n.head.text, ...n.templateSpans.map((s) => s.literal.text)]
      const exprs = n.templateSpans.map((s) => rewrite(s.expression))
      count++
      const call = templateCall(parts, exprs)
      return ts.isJsxAttribute(n.parent) ? `{${call}}` : call
    }
    return null
  }
  function ignored(n) {
    const l = sf.getLineAndCharacterOfPosition(n.getStart(sf)).line
    return src.split('\n')[l].includes('i18n-ignore')
  }
  function hasCjkOwn(n) {
    return CJK.test(n.head.text) || n.templateSpans.some((s) => CJK.test(s.literal.text))
  }
  function containsJsx(e) {
    let f = false
    const v = (x) => {
      if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x) || ts.isJsxFragment(x)) f = true
      else ts.forEachChild(x, v)
    }
    v(e)
    return f
  }

  let out = rewrite(sf)
  out = src.slice(0, sf.getStart(sf)) + out
  if (count) {
    total += count
    console.log(`${count}\t${file}${shadow ? '  (alias tr)' : ''}`)
    if (WRITE) {
      let rel = relative(dirname(file), 'src/lib/i18n').replace(/\\/g, '/')
      if (!rel.startsWith('.')) rel = './' + rel
      const imp = shadow ? `import { t as tr } from '${rel}'\n` : `import { t } from '${rel}'\n`
      // 放在最后一个 import 后
      const lastImport = [...sf.statements].filter((s) => ts.isImportDeclaration(s)).pop()
      if (lastImport) {
        const off = sf.getStart(sf)
        const endPos = lastImport.getEnd() - off
        out = src.slice(0, off) + rewrite(sf).slice(0, endPos) + '\n' + imp.trimEnd() + rewrite(sf).slice(endPos)
      } else out = imp + out
      writeFileSync(file, out)
    }
  }
}
console.log('total', total)
if (process.argv.includes('--check') && total > 0) process.exitCode = 1
console.log('\n— 未包（数据用途，人工核对）—')
console.log(report.join('\n'))
