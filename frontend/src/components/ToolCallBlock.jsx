import { useState } from 'react'
import { Wrench, ChevronDown, ChevronRight, Check, Loader } from 'lucide-react'

export default function ToolCallBlock({ toolCalls }) {
  const [openId, setOpenId] = useState(null)

  if (!toolCalls?.length) return null

  return (
    <div className="space-y-1">
      {toolCalls.map((tc, i) => {
        const key = tc.id || i
        const isOpen = openId === key

        // Normalize: support both agent-mode {tool_name, arguments} and OpenAI {function: {name, arguments}}
        const name = tc.tool_name || tc.function?.name || tc.name || 'tool'
        const args = tc.arguments || tc.function?.arguments
        const result = tc.result
        const isDone = tc.status === 'done' || (result !== undefined && result !== null)

        return (
          <div key={key} className="rounded-lg border border-edge/70 overflow-hidden bg-elevated/30">
            <button
              onClick={() => setOpenId(isOpen ? null : key)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-[12px] hover:bg-hover/30 transition-colors"
            >
              <Wrench size={11} className="text-accent shrink-0" />
              <span className="text-ink-secondary font-mono truncate">{name}</span>
              {/* compact args preview */}
              {args && !isOpen && (
                <span className="text-ink-muted truncate text-[11px] flex-1 text-left">
                  {formatArgsCompact(args)}
                </span>
              )}
              <span className="flex-1" />
              {isDone
                ? <Check size={11} className="text-jade shrink-0" />
                : <Loader size={11} className="text-accent animate-spin shrink-0" />}
              {isOpen ? <ChevronDown size={11} className="shrink-0" /> : <ChevronRight size={11} className="shrink-0" />}
            </button>

            {isOpen && (
              <div className="border-t border-edge/50 text-[12px]">
                {args && (
                  <div className="px-3 py-1.5">
                    <pre className="text-ink-muted font-mono whitespace-pre-wrap break-all">
                      {typeof args === 'string' ? args : JSON.stringify(args, null, 2)}
                    </pre>
                  </div>
                )}
                {isDone && result != null && (
                  <div className="px-3 py-1.5 border-t border-edge/50">
                    <pre className="text-ink-secondary font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                      {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function formatArgsCompact(args) {
  if (typeof args === 'string') {
    try { args = JSON.parse(args) } catch { return args.slice(0, 60) }
  }
  if (typeof args !== 'object' || args === null) return String(args)
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
    .slice(0, 80)
}
