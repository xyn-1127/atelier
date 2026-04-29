import { useState } from 'react'
import { ChevronDown, ChevronRight, Brain } from 'lucide-react'

export default function ThinkingBlock({ content, isStreaming }) {
  const [open, setOpen] = useState(false)

  // Only render when there is actual content or actively streaming reasoning
  if (!content && !isStreaming) return null

  return (
    <div className="mb-2 rounded-xl border border-edge overflow-hidden bg-surface/50">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-ink-secondary hover:text-ink transition-colors"
      >
        <Brain size={13} className="text-accent" />
        <span className="font-medium">深度思考</span>
        {isStreaming && (
          <span className="flex gap-0.5 ml-1">
            <span className="w-1 h-1 rounded-full bg-accent anim-pulse" />
            <span className="w-1 h-1 rounded-full bg-accent anim-pulse" style={{ animationDelay: '200ms' }} />
            <span className="w-1 h-1 rounded-full bg-accent anim-pulse" style={{ animationDelay: '400ms' }} />
          </span>
        )}
        <span className="flex-1" />
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>

      {open && content && (
        <div className="px-3 pb-3 pt-1 text-[12px] text-ink-muted leading-relaxed whitespace-pre-wrap border-t border-edge max-h-60 overflow-y-auto">
          {content}
        </div>
      )}
    </div>
  )
}
