import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, Loader } from 'lucide-react'
import ToolCallBlock from './ToolCallBlock'
import Markdown from './Markdown'
import { useLang } from '../i18n'

export default function AgentStepCard({ step, className = '' }) {
  const [open, setOpen] = useState(true)
  const { t } = useLang()

  const label = t(`agent.${step.agent_name}`) || step.agent_name
  const isRunning = step.status === 'running'
  const isDone = step.status === 'done'
  const dur = step.metrics?.duration_ms
  const tokens = step.metrics?.tokens?.total_tokens
  const entries = step.tool_calls || []
  const hasEntries = entries.length > 0

  return (
    <div className={`rounded-xl border border-edge overflow-hidden bg-surface/40 anim-fade ${className}`}>
      {/* header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-start gap-2 px-3.5 py-2.5 hover:bg-hover/30 transition-colors text-left"
      >
        <span className="mt-0.5">
          {isRunning
            ? <Loader size={14} className="text-accent animate-spin" />
            : <CheckCircle2 size={14} className="text-jade" />}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-accent">{label}</span>
            {isDone && (dur != null || tokens != null) && (
              <span className="text-[11px] text-ink-muted">
                {[dur != null && `${(dur / 1000).toFixed(1)}s`, tokens != null && `${tokens} tokens`].filter(Boolean).join(' · ')}
              </span>
            )}
          </div>
          <div className="text-[13px] text-ink-muted break-words">{step.task}</div>
        </div>

        {open ? <ChevronDown size={13} className="text-ink-muted shrink-0" /> : <ChevronRight size={13} className="text-ink-muted shrink-0" />}
      </button>

      {/* body */}
      {open && (
        <div className="border-t border-edge">
          {/* interleaved thinking + tool calls — collapsed with scroll */}
          {hasEntries && (
            <div className="max-h-52 overflow-y-auto border-b border-edge/50">
              {entries.map((entry, i) =>
                entry.type === 'thinking' ? (
                  <div key={`e-${i}`} className="px-3.5 py-1.5 text-[12px] text-ink-muted leading-relaxed border-b border-edge/30 last:border-b-0">
                    <Markdown>{entry.content}</Markdown>
                  </div>
                ) : (
                  <div key={`e-${i}`} className="px-3 py-1 border-b border-edge/30 last:border-b-0">
                    <ToolCallBlock toolCalls={[entry]} />
                  </div>
                )
              )}
            </div>
          )}

          {/* step final content — visually distinct, full size */}
          {step.content && (
            <div className="px-3.5 py-2.5 text-[14px] text-ink-secondary leading-relaxed">
              <Markdown>{step.content}</Markdown>
            </div>
          )}

          {/* running indicator */}
          {isRunning && !step.content && !hasEntries && (
            <div className="px-3.5 py-3 flex items-center gap-2 text-[13px] text-ink-muted">
              <Loader size={13} className="animate-spin" />
              <span>{t('agent.running')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
