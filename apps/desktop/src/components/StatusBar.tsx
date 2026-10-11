import { useEffect, useState } from 'react'
import { Cpu, Wallet } from 'lucide-react'
import { gateStatus } from '../data/budget'
import { useLedger } from '../lib/ledger'
import { APP_VERSION } from '../lib/version'
import { Tip } from './Tip'
import { t as tr } from '../lib/i18n'

export function StatusBar() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  const gate = gateStatus(now)
  const led = useLedger()
  // 0.3.2：只显示累计已花（本机账本），不再有总额 / 剩余
  const spent = led.status === 'ok' ? `¥${led.data.spent.toFixed(2)}` : '¥—'

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border-soft bg-parchment-deep/70 px-3 text-[10.5px] text-sepia">
      <div className="flex items-center gap-1">
        <Tip label="deepseek-flash" side="top-start">
          <span className="sb-item">
            <Cpu size={11} strokeWidth={1.7} />
            Flash
          </span>
        </Tip>
        <Tip label={tr('DeepSeek 高峰时段 2× 价，照常可用 · 北京时间 {0}', gate.next)} side="top">
          <span className="sb-item">
            <span className={`h-1.5 w-1.5 rounded-full ${gate.inPeak ? 'bg-rose-ink' : 'bg-sage'}`} />
            {gate.inPeak ? tr('高峰') : tr('空闲')}
          </span>
        </Tip>
      </div>
      <div className="flex items-center gap-1">
        <Tip label={led.status === 'ok' ? tr('本机累计已花（账本）') : tr('未连接核心，用量未知')} side="top-end">
          <span className="sb-item tabular-nums" data-testid="status-spent">
            <Wallet size={11} strokeWidth={1.7} />
            {spent}
          </span>
        </Tip>
        <span className="sb-item text-sepia-muted">v{APP_VERSION}</span>
      </div>
    </footer>
  )
}
