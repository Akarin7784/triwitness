import { AnimatePresence, motion } from 'framer-motion'
import { useToasts } from '../lib/toast'

export function Toaster() {
  const list = useToasts()
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-16 z-50 flex flex-col items-center gap-2">
      <AnimatePresence>
        {list.map((t) => (
          <motion.div
            key={t.id}
            data-testid="toast"
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ pointerEvents: 'none', opacity: 0, y: 6, transition: { duration: 0.2 } }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            className="rounded-full bg-ink/90 px-4 py-1.5 text-[13px] text-parchment shadow-lg"
          >
            {t.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
