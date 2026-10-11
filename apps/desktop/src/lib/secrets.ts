/**
 * API 密钥（UI-21）：存系统凭据库，只在桌面应用里可用（Tauri secrets.rs）。
 * v1.0：kind = 'github' 存开 PR 用的 GitHub 令牌（同一个凭据库，不同账户名）。
 * 前端只能写入 / 清除 / 查询是否已设置，明文永不回传。浏览器预览返回 'unsupported'。
 */
import { invoke } from '@tauri-apps/api/core'

export type SecretState = 'set' | 'unset' | 'unsupported'
export type SecretKind = 'deepseek' | 'github'

const inTauri = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export async function secretStatus(kind: SecretKind = 'deepseek'): Promise<SecretState> {
  if (!inTauri()) return 'unsupported'
  return (await invoke<boolean>('secret_status', { kind })) ? 'set' : 'unset'
}

export async function secretSet(value: string, kind: SecretKind = 'deepseek'): Promise<void> {
  await invoke('secret_set', { value, kind })
}

export async function secretClear(kind: SecretKind = 'deepseek'): Promise<void> {
  await invoke('secret_clear', { kind })
}
