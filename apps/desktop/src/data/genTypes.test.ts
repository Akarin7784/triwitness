import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

describe('tw-events.gen.ts', () => {
  it('与 schemas/tw-events-1.schema.json 同步', () => {
    const script = fileURLToPath(new URL('../../scripts/gen-event-types.mjs', import.meta.url))
    expect(() => execFileSync('node', [script, '--check'], { stdio: 'pipe' })).not.toThrow()
  }, 20_000)
})
