/**
 * API 密钥（UI-21）：存系统凭据库，只在桌面应用里可用（Tauri secrets.rs）。
 * 前端只能写入 / 清除 / 查询是否已设置，明文永不回传。浏览器预览返回 'unsupported'。
 */
import { invoke } from '@tauri-apps/api/core'

export type SecretState = 'set' | 'unset' | 'unsupported'

const inTauri = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export async function secretStatus(): Promise<SecretState> {
  if (!inTauri()) return 'unsupported'
  return (await invoke<boolean>('secret_status')) ? 'set' : 'unset'
}

export async function secretSet(value: string): Promise<void> {
  await invoke('secret_set', { value })
}

export async function secretClear(): Promise<void> {
  await invoke('secret_clear')
}
