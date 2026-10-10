import clsx from 'clsx'
import type { ReactNode } from 'react'

/** 暖色悬停提示：替代界面上的说明文字。延迟出现、柔和淡入。 */
export function Tip({
  label,
  children,
  side = 'top',
  className,
}: {
  label: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right' | 'top-end' | 'top-start'
  className?: string
}) {
  return (
    <span className={clsx('tip-host relative inline-flex', className)}>
      {children}
      <span role="tooltip" className={clsx('tip', `tip-${side}`)}>
        {label}
      </span>
    </span>
  )
}
