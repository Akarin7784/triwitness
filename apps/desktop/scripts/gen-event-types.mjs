// 从 schemas/tw-events-1.schema.json 生成 TS 类型（单一事实来源：core 的 pydantic 模型）
// 用法：npm run gen:events            生成
//       npm run gen:events -- --check  只校验生成物是否最新（CI 用）
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript'

const schemaPath = fileURLToPath(new URL('../../../schemas/tw-events-1.schema.json', import.meta.url))
const outPath = fileURLToPath(new URL('../src/data/tw-events.gen.ts', import.meta.url))

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'))
const ts = await compile(schema, 'TwEvent', {
  bannerComment:
    '/* eslint-disable */\n// 由 scripts/gen-event-types.mjs 从 schemas/tw-events-1.schema.json 生成，勿手改。\n// 重新生成：npm run gen:events',
  additionalProperties: false,
  strictIndexSignatures: false,
  unreachableDefinitions: true,
  style: { singleQuote: true, semi: false, printWidth: 110 },
})

if (process.argv.includes('--check')) {
  const current = readFileSync(outPath, 'utf8')
  if (current !== ts) {
    console.error('tw-events.gen.ts 已过期：运行 npm run gen:events')
    process.exit(1)
  }
  console.log('tw-events.gen.ts 是最新的')
} else {
  writeFileSync(outPath, ts)
  console.log('写入', outPath)
}
