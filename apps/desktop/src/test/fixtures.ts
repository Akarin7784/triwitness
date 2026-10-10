// 测试辅助：直接从仓库根读取 golden fixture（与 app 用的是同一份文件）
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const FIXTURE_FILES = ['success', 'failure', 'budget_exceeded'] as const
export type FixtureFile = (typeof FIXTURE_FILES)[number]

export function readFixture(name: FixtureFile): string {
  return readFileSync(fileURLToPath(new URL(`../../../../evals/fixtures/events/${name}.jsonl`, import.meta.url)), 'utf8')
}
