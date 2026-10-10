import { describe, expect, it } from 'vitest'
import { bytesToB64, classify, formatSize, textToB64 } from './attachments'

describe('attachments', () => {
  it('按扩展名 / MIME 分类', () => {
    expect(classify('a.png')).toBe('image')
    expect(classify('x', 'image/jpeg')).toBe('image')
    expect(classify('main.py')).toBe('text')
    expect(classify('Makefile')).toBe('text')
    expect(classify('data', 'application/json')).toBe('text')
    expect(classify('a.zip')).toBe('binary')
  })
  it('大小与 base64', () => {
    expect(formatSize(512)).toBe('512 B')
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(3 * 1024 * 1024)).toBe('3.0 MB')
    expect(textToB64('中文')).toBe(Buffer.from('中文').toString('base64'))
    const big = new Uint8Array(70000).fill(65)
    expect(bytesToB64(big)).toBe(Buffer.from(big).toString('base64'))
  })
})
