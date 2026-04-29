import { useState } from 'react'
import { ChevronDown, ChevronRight, Lightbulb, CheckCircle2, Loader, Circle } from 'lucide-react'
import { useLang } from '../i18n'

const STATUS_ICON = {
  done:    <CheckCircle2 size={13} className="text-jade shrink-0" />,
  running: <Loader size={13} className="text-accent animate-spin shrink-0" />,
  pending: <Circle size={13} className="text-ink-muted shrink-0" />,
}

export default function PlanBlock({ plan }) {
  const [open, setOpen] = useState(true)
  const { t } = useLang()

  if (!plan?.steps?.length) return null

  const doneCount = plan.steps.filter(s => s.status === 'done').length

  return (
    <div className="mb-3 rounded-xl border border-edge overflow-hidden bg-surface/60 anim-fade">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3.5 py-2.5 text-[13px] text-ink-secondary hover:text-ink transition-colors"
      >
        <Lightbulb size={13} className="text-accent shrink-0" />
        <span className="font-medium">{t('plan.title')}</span>
        <span className="text-ink-muted">({doneCount}/{plan.steps.length})</span>
        <span className="flex-1" />
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>

      {open && (
        <div className="border-t border-edge px-3.5 py-2.5 space-y-1.5">
          {/* reasoning */}
          {plan.reasoning && (
            <p className="text-[12px] text-ink-muted italic leading-relaxed mb-2">{plan.reasoning}</p>
          )}

          {/* steps */}
          {plan.steps.map((step, i) => {
            const deps = step.depends_on || []
            return (
              <div
                key={i}
                className={`flex items-start gap-2 py-1 ${deps.length > 0 ? 'ml-4' : ''}`}
              >
                {STATUS_ICON[step.status] || STATUS_ICON.pending}
                <div className="min-w-0">
                  <span className="text-[13px] font-mono text-accent mr-1.5">{step.agent_name}</span>
                  <span className="text-[13px] text-ink-secondary">{step.task}</span>
                  {deps.length > 0 && (
                    <span className="text-[10px] text-ink-muted ml-2">
                      {t('plan.depends_on')} {deps.join(', ')}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
