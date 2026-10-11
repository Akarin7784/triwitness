import { useState } from 'react'
import { LifeBuoy } from 'lucide-react'
import { exportDiagnostics } from '../lib/diag'
import { revealPath } from '../lib/open'
import { toast } from '../lib/toast'
import { t } from '../lib/i18n'

/** 「导出诊断包」：打 zip（脱敏）→ 在文件管理器里定位；浏览器预览里只提示路径。 */
export function DiagButton({ runId, label, testId = 'export-diag' }: { runId?: string | null; label?: string; testId?: string }) {
  const [busy, setBusy] = useState(false)
  const go = async () => {
    if (busy) return
    setBusy(true)
    const r = await exportDiagnostics(runId)
    setBusy(false)
    if (!r.ok) return toast(t('导出诊断包失败：{0}', r.error))
    const kb = Math.max(1, Math.round(r.data.bytes / 1024))
    toast(t('诊断包已导出（{0} 个文件，{1} KB，密钥已脱敏）：{2}', String(r.data.files), String(kb), r.data.path))
    void revealPath(r.data.path)
  }
  return (
    <button type="button" className="chip hover:text-amber-ink" data-testid={testId} disabled={busy} onClick={() => void go()}>
      <LifeBuoy size={11} strokeWidth={1.7} />
      {busy ? t('正在导出…') : (label ?? t('导出诊断包'))}
    </button>
  )
}
