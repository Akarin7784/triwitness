import { useState } from 'react'
import { ExternalLink, KeyRound, Lock } from 'lucide-react'
import { Btn, Dialog, DialogActions } from './Dialog'
import { FIELD } from '../lib/ui'
import { secretSet } from '../lib/secrets'
import { openUrl } from '../lib/open'
import { toast } from '../lib/toast'
import { t as tr } from '../lib/i18n'

export const DEEPSEEK_KEYS_URL = 'https://platform.deepseek.com/api_keys'

/**
 * 首次使用（0.3.1，照 Claude 的引导）：还没有 DeepSeek API 密钥时弹出，粘贴后存系统凭据库（明文不回传）。
 * 没填密钥就发送也会弹它，而不是让任务失败。
 */
export function ApiKeyDialog({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title={tr('连接 DeepSeek')} testId="api-key-dialog" width={460}>
      {open && <Body onClose={onClose} onSaved={onSaved} />}
    </Dialog>
  )
}

function Body({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [v, setV] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const key = v.trim()
  const valid = /^sk-[A-Za-z0-9_-]{16,}$/.test(key)
  const save = async () => {
    if (!valid || busy) return
    setBusy(true)
    setErr(null)
    try {
      await secretSet(key)
      toast(tr('已存入系统凭据库'))
      onSaved()
      onClose()
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <p className="text-[13px] leading-relaxed text-ink-soft" data-allow-wrap>
        {tr('三证用你自己的 DeepSeek 账户调用模型（只用 deepseek-flash）。粘贴一个 API 密钥就能开始；费用记在本机账本里，受预算上限约束。')}
      </p>
      <button
        type="button"
        data-testid="api-key-get"
        onClick={() => void openUrl(DEEPSEEK_KEYS_URL).then((ok) => ok || toast(tr('打不开浏览器：{0}', DEEPSEEK_KEYS_URL)))}
        className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] text-amber-ink hover:underline"
      >
        <ExternalLink size={12} strokeWidth={1.8} />
        {tr('去 DeepSeek 开放平台创建密钥')}
      </button>
      <label className="mt-4 block">
        <span className="mb-1.5 flex items-center gap-1.5 text-[12px] text-sepia">
          <KeyRound size={12} strokeWidth={1.7} /> {tr('API 密钥')}
        </span>
        <input
          autoFocus
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={v}
          data-testid="api-key-input"
          onChange={(e) => setV(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent.isComposing && void save()}
          placeholder="sk-…"
          className={FIELD}
          aria-label={tr('API 密钥')}
        />
      </label>
      <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-sepia-muted">
        <Lock size={10} strokeWidth={2} /> {tr('只存进系统凭据库（Windows 凭据管理器），不会写进文件或日志。')}
      </p>
      {key && !valid && <p className="mt-1 text-[11.5px] text-rose-ink">{tr('看起来不像 DeepSeek 密钥（应以 sk- 开头）')}</p>}
      {err && <p className="mt-1 text-[11.5px] text-rose-ink">{err}</p>}
      <DialogActions>
        <Btn onClick={onClose}>{tr('稍后')}</Btn>
        <Btn kind="solid" onClick={() => void save()} disabled={!valid || busy} testId="api-key-save">
          {tr('保存并继续')}
        </Btn>
      </DialogActions>
    </>
  )
}
