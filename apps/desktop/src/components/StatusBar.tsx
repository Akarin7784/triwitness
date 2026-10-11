import { useEffect, useState } from 'react'
import { Cpu, Wallet } from 'lucide-react'
import { BUDGET_TOTAL, gateStatus } from '../data/budget'
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
  const left = led.status === 'ok' ? `¥${led.data.remaining.toFixed(2)}` : '¥—'
  const total = led.status === 'ok' ? led.data.total_cny : BUDGET_TOTAL

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border-soft bg-parchment-deep/70 px-3 text-[10.5px] text-sepia">
      <div className="flex items-center gap-1">
        <Tip label="deepseek-flash" side="top-start">
          <span className="sb-item">
            <Cpu size={11} strokeWidth={1.7} />
            Flash
          </span>
        </Tip>
        <Tip label={tr('北京时间 · {0}', gate.next)} side="top">
          <span className="sb-item">
            <span className={`h-1.5 w-1.5 rounded-full ${gate.inPeak ? 'bg-rose-ink' : 'bg-sage'}`} />
            {gate.inPeak ? tr('高峰') : tr('空闲')}
          </span>
        </Tip>
      </div>
      <div className="flex items-center gap-1">
        <Tip label={led.status === 'ok' ? tr('余额 / ¥{0}', total) : tr('未连接核心，余额未知')} side="top-end">
          <span className="sb-item tabular-nums">
            <Wallet size={11} strokeWidth={1.7} />
            {left}
          </span>
        </Tip>
        <span className="sb-item text-sepia-muted">v{APP_VERSION}</span>
      </div>
    </footer>
  )
}
