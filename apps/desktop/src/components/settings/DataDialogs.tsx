/** 隐私：清除会话记录确认 · 关于：开源许可（UI-21 第 3 轮） */
import { Dialog, DialogActions, Btn } from '../Dialog'
import { t } from '../../lib/i18n'

export function ClearHistoryDialog({ open, onClose, onConfirm }: { open: boolean; onClose: () => void; onConfirm: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title={t('清除本机会话记录')} width={460} testId="clear-dialog">
      <p className="text-[13.5px] leading-relaxed text-ink-soft">{t('会话列表、版本、反馈和草稿会从这台电脑上删掉，无法恢复。')}</p>
      <p className="mt-2 text-[12.5px] leading-relaxed text-sepia-muted">{t('设置、项目和磁盘上的任务证据（~/.triwitness/runs）保留。')}</p>
      <DialogActions>
        <Btn onClick={onClose}>{t('取消')}</Btn>
        <Btn kind="danger" primary testId="clear-confirm" onClick={onConfirm}>
          {t('清除')}
        </Btn>
      </DialogActions>
    </Dialog>
  )
}

const LICENSES: [string, string][] = [
  ['React / React DOM', 'MIT'],
  ['Tauri', 'Apache-2.0 / MIT'],
  ['framer-motion', 'MIT'],
  ['lucide-react', 'ISC'],
  ['react-markdown · remark-gfm', 'MIT'],
  ['clsx', 'MIT'],
  ['Tailwind CSS', 'MIT'],
  ['Noto Serif SC · Noto Sans SC · JetBrains Mono', 'OFL-1.1'],
  ['keyring (Rust)', 'Apache-2.0 / MIT'],
  ['serde · base64 · dirs (Rust)', 'Apache-2.0 / MIT'],
]

export function LicensesDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title={t('开源许可')} width={520} testId="licenses-dialog">
      <p className="text-[12.5px] leading-relaxed text-sepia-muted">{t('三证用到的主要开源组件，感谢它们的作者。')}</p>
      <ul className="mt-3 divide-y divide-border-soft/70 rounded-xl border border-border-soft/80">
        {LICENSES.map(([name, lic]) => (
          <li key={name} className="flex items-center justify-between gap-3 px-3 py-2 text-[13px]">
            <span className="min-w-0 truncate text-ink">{name}</span>
            <span className="shrink-0 font-mono text-[11.5px] text-sepia">{lic}</span>
          </li>
        ))}
      </ul>
      <DialogActions>
        <Btn kind="solid" primary onClick={onClose}>
          {t('知道了')}
        </Btn>
      </DialogActions>
    </Dialog>
  )
}
