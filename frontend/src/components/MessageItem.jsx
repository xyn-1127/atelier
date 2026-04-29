import { useState } from 'react'
import { Loader, Bot, ChevronDown, ChevronRight } from 'lucide-react'
import ThinkingBlock from './ThinkingBlock'
import ToolCallBlock from './ToolCallBlock'
import PlanBlock from './PlanBlock'
import AgentStepCard from './AgentStepCard'
import Markdown from './Markdown'
import { useLang } from '../i18n'

/** Group agent steps into parallel waves based on plan dependencies */
function computeWaves(plan, agentSteps) {
  if (!agentSteps?.length) return []
  if (!plan?.steps?.length) return agentSteps.map(s => [s])

  const planSteps = plan.steps
  const waves = []
  const assigned = new Set()

  while (assigned.size < planSteps.length) {
    const waveIndices = []
    planSteps.forEach((ps, i) => {
      if (assigned.has(i)) return
      if ((ps.depends_on || []).every(d => assigned.has(d))) waveIndices.push(i)
    })
    if (waveIndices.length === 0) break
    waveIndices.forEach(i => assigned.add(i))
    const waveSteps = waveIndices.map(i => agentSteps[i]).filter(Boolean)
    if (waveSteps.length) waves.push(waveSteps)
  }

  for (let i = planSteps.length; i < agentSteps.length; i++) {
    waves.push([agentSteps[i]])
  }
  return waves
}

export default function MessageItem({ message, isStreaming, isThinking }) {
  const { t } = useLang()
  const isUser = message.role === 'user'
  const [agentOpen, setAgentOpen] = useState(true)

  const msgToolCalls = (() => {
    if (message.tool_calls && Array.isArray(message.tool_calls)) return message.tool_calls
    if (!message.tool_calls_json) return []
    try {
      const parsed = typeof message.tool_calls_json === 'string'
        ? JSON.parse(message.tool_calls_json) : message.tool_calls_json
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  })()

  const hasAgentSteps = message.agent_steps?.length > 0
  const hasPlan = !!message.plan
  const hasAgentProcess = hasPlan || hasAgentSteps
  const waves = computeWaves(message.plan, message.agent_steps)
  const hasReasoning = !!(message.reasoning_content && message.reasoning_content.trim())
  const messageLevelTools = msgToolCalls.filter(tc => tc.type !== 'thinking')

  const runningCount = hasAgentSteps ? message.agent_steps.filter(s => s.status === 'running').length : 0
  const doneCount = hasPlan
    ? message.plan.steps.filter(s => s.status === 'done').length
    : hasAgentSteps ? message.agent_steps.filter(s => s.status === 'done').length : 0
  const totalCount = hasPlan ? message.plan.steps.length : (message.agent_steps?.length || 0)

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} anim-fade`}>
      <div className={isUser ? 'max-w-[80%]' : 'max-w-[90%] w-full'}>

        {/* 1. Thinking block */}
        {hasReasoning && (
          <ThinkingBlock content={message.reasoning_content} isStreaming={isStreaming && isThinking} />
        )}

        {/* 2. Collapsible agent process (plan + steps) */}
        {hasAgentProcess && (
          <div className="mb-3 rounded-xl border border-edge overflow-hidden">
            <button
              onClick={() => setAgentOpen(v => !v)}
              className="w-full flex items-center gap-2 px-3.5 py-2.5 text-[13px] text-ink-secondary hover:text-ink bg-surface/40 transition-colors"
            >
              <Bot size={14} className="text-accent shrink-0" />
              <span className="font-medium">{t('chat.process')}</span>
              {totalCount > 0 && (
                <span className="text-ink-muted">({doneCount}/{totalCount})</span>
              )}
              {runningCount > 0 && (
                <Loader size={13} className="animate-spin text-accent" />
              )}
              <span className="flex-1" />
              {agentOpen
                ? <ChevronDown size={14} className="shrink-0" />
                : <ChevronRight size={14} className="shrink-0" />}
            </button>
            {agentOpen && (
              <div className="px-3 py-2.5 space-y-2 border-t border-edge">
                {hasPlan && <PlanBlock plan={message.plan} />}
                {waves.map((wave, wi) => (
                  <div key={wi} className={wave.length > 1 ? 'flex gap-2' : ''}>
                    {wave.map((step, si) => (
                      <AgentStepCard
                        key={`${wi}-${si}`}
                        step={step}
                        className={wave.length > 1 ? 'flex-1 min-w-0' : ''}
                      />
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 3. Message-level tool calls (non-agent mode) */}
        {!hasAgentSteps && messageLevelTools.length > 0 && (
          <div className="mb-2">
            <ToolCallBlock toolCalls={messageLevelTools} />
          </div>
        )}

        {/* 4. Content */}
        {isUser ? (
          <div className="msg-user rounded-2xl px-4 py-3 text-[15px] leading-relaxed bg-accent text-deep">
            <div className="whitespace-pre-wrap break-words">{message.content}</div>
          </div>
        ) : message.content ? (
          <div className="rounded-2xl px-4 py-3 text-[15px] leading-relaxed bg-surface text-ink">
            <Markdown>{message.content}</Markdown>
            {isStreaming && !isThinking && (
              <div className="flex gap-1 mt-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-accent anim-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-accent anim-pulse" style={{ animationDelay: '200ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-accent anim-pulse" style={{ animationDelay: '400ms' }} />
              </div>
            )}
          </div>
        ) : isStreaming && !isThinking && !hasReasoning && !hasAgentProcess && messageLevelTools.length === 0 ? (
          <div className="flex items-center gap-2 py-2 text-ink-muted text-[14px]">
            <Loader size={14} className="animate-spin" />
            <span>{t('chat.thinking')}</span>
          </div>
        ) : null}
      </div>
    </div>
  )
}
