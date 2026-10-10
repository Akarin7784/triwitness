import type { Phase } from '../data/mapEvent'

export const PHASE_DOT: Record<Phase, string> = {
  idle: 'bg-border',
  active: 'bg-amber pulse-dot',
  waiting: 'bg-sepia',
  done: 'bg-sage',
  failed: 'bg-rose-ink',
  budget: 'bg-amber',
  cancelled: 'bg-sepia-muted',
}
