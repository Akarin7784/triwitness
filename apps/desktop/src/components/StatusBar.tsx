import { useEffect, useMemo, useState } from 'react'
import { Cpu, Wallet } from 'lucide-react'
import { BUDGET_TOTAL, gateStatus, ledger, rowCost } from '../data/budget'
import { Tip } from './Tip'

export function StatusBar() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  const gate = gateStatus(now)
  const left = useMemo(() => BUDGET_TOTAL - ledger.reduce((s, r) => s + rowCost(r), 0), [])

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border-soft bg-parchment-deep/70 px-3 text-[10.5px] text-sepia">
      <div className="flex items-center gap-1">
        <Tip label="deepseek-flash" side="top-start">
          <span className="sb-item">
            <Cpu size={11} strokeWidth={1.7} />
            Flash
          </span>
        </Tip>
        <Tip label={`北京时间 · ${gate.next}`} side="top">
          <span className="sb-item">
            <span className={`h-1.5 w-1.5 rounded-full ${gate.inPeak ? 'bg-rose-ink' : 'bg-sage'}`} />
            {gate.inPeak ? '高峰' : '空闲'}
          </span>
        </Tip>
      </div>
      <div className="flex items-center gap-1">
        <Tip label={`余额 / ¥${BUDGET_TOTAL}`} side="top-end">
          <span className="sb-item tabular-nums">
            <Wallet size={11} strokeWidth={1.7} />¥{left.toFixed(2)}
          </span>
        </Tip>
        <span className="sb-item text-sepia-muted">v0.1</span>
      </div>
    </footer>
  )
}
