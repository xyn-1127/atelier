import { useState, useEffect, useRef } from 'react'
import { fetchChat, sendMessageStream, resumeMessageStream } from '../api/chat'
import { Send, Brain, Bot, PanelRightOpen, PanelRightClose, StopCircle } from 'lucide-react'
import MessageItem from './MessageItem'
import { useLang } from '../i18n'

/** Parse execution_json from loaded messages into display-ready fields */
function enrichMessages(msgs) {
  return msgs.map(m => {
    if (!m.execution_json) return m
    try {
      const exec = typeof m.execution_json === 'string' ? JSON.parse(m.execution_json) : m.execution_json
      return {
        ...m,
        plan: exec.plan ? {
          ...exec.plan,
          steps: (exec.plan.steps || []).map(s => ({ ...s, status: s.status || 'done' })),
        } : null,
        agent_steps: (exec.agent_steps || []).map(s => ({
          ...s,
          status: s.status || 'done',
          tool_calls: (s.tool_calls || []).map(tc => ({ ...tc, status: tc.status || 'done' })),
        })),
      }
    } catch { return m }
  })
}

export default function ChatView({ chatId, workspaceId, showNotes, onToggleNotes, onChatsChanged }) {
  const { t } = useLang()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingMsg, setStreamingMsg] = useState(null)
  const [isThinking, setIsThinking] = useState(false)
  const [useThinking, setUseThinking] = useState(false)
  const [useAgent, setUseAgent] = useState(false)
  const [error, setError] = useState(null)

  const abortRef = useRef(null)
  const bottomRef = useRef(null)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const atBottomRef = useRef(true)

  /* ── helpers ── */
  function updateStream(fn) {
    setStreamingMsg(prev => prev ? fn(prev) : prev)
  }

  /**
   * Update a specific agent step by its plan step_index.
   * _stepsMap is { [stepIndex]: stepData }; auto-creates a placeholder
   * if the step_start hasn't arrived yet (events can race in parallel).
   */
  function updateStep(stepIndex, fn) {
    if (stepIndex === null || stepIndex === undefined) return false
    setStreamingMsg(prev => {
      if (!prev) return prev
      const stepsMap = { ...(prev._stepsMap || {}) }
      const existing = stepsMap[stepIndex] || {
        agent_name: `step_${stepIndex}`,
        task: '',
        status: 'running',
        tool_calls: [],
        content: '',
      }
      stepsMap[stepIndex] = fn(existing)
      return {
        ...prev,
        _stepsMap: stepsMap,
        agent_steps: buildStepsArray(stepsMap),
      }
    })
    return true
  }

  function stopStream() {
    setStreaming(false)
    setIsThinking(false)
    setStreamingMsg(null)
  }

  function handleStreamErr(err) {
    if (err.name !== 'AbortError') { setError(err.message); stopStream() }
  }

  function reloadChat() {
    if (!chatId) return
    fetchChat(chatId).then(chat => {
      setMessages(enrichMessages(chat.messages || []))
    }).catch(e => setError(e.message))
  }

  /* ── streaming callbacks ── */
  function makeCallbacks(extra = {}) {
    return {
      ...extra,

      onReasoningChunk: (chunk) => {
        setIsThinking(true)
        updateStream(m => ({ ...m, reasoning_content: (m.reasoning_content || '') + chunk }))
      },

      onChunk: (chunk, si) => {
        setIsThinking(false)
        if (si != null && !updateStep(si, s => ({ ...s, content: (s.content || '') + chunk }))) {
          updateStream(m => ({ ...m, content: (m.content || '') + chunk }))
        } else if (si == null) {
          updateStream(m => ({ ...m, content: (m.content || '') + chunk }))
        }
      },

      onContentToThinking: (text, si) => {
        const entry = { type: 'thinking', content: text }
        if (si != null && !updateStep(si, s => ({
          ...s, content: '', tool_calls: [...(s.tool_calls || []), entry],
        }))) {
          updateStream(m => ({
            ...m, content: '', tool_calls: [...(m.tool_calls || []), entry],
          }))
        } else if (si == null) {
          updateStream(m => ({
            ...m, content: '', tool_calls: [...(m.tool_calls || []), entry],
          }))
        }
      },

      onToolCall: (data, si) => {
        const entry = { ...data, status: 'running', result: null }
        if (si != null && !updateStep(si, s => ({ ...s, tool_calls: [...(s.tool_calls || []), entry] }))) {
          updateStream(m => ({ ...m, tool_calls: [...(m.tool_calls || []), entry] }))
        } else if (si == null) {
          updateStream(m => ({ ...m, tool_calls: [...(m.tool_calls || []), entry] }))
        }
      },

      onToolResult: (data, si) => {
        const apply = s => ({
          ...s,
          tool_calls: (s.tool_calls || []).map(tc =>
            tc.tool_name === data.tool_name && tc.status === 'running'
              ? { ...tc, status: 'done', result: data.result }
              : tc
          ),
        })
        if (si != null && !updateStep(si, apply)) {
          updateStream(m => apply({ tool_calls: m.tool_calls || [] }))
        } else if (si == null) {
          updateStream(m => apply({ tool_calls: m.tool_calls || [] }))
        }
      },

      onPlan: data => {
        const plan = { ...data, steps: data.steps.map(s => ({ ...s, status: 'pending' })) }
        updateStream(m => ({ ...m, plan, _stepsMap: {}, agent_steps: [] }))
      },

      onStepStart: data => {
        setStreamingMsg(prev => {
          if (!prev) return prev
          const newStep = {
            agent_name: data.agent_name,
            task: data.task,
            status: 'running',
            tool_calls: [],
            content: '',
          }
          const stepsMap = { ...(prev._stepsMap || {}), [data.index]: newStep }
          return {
            ...prev,
            _stepsMap: stepsMap,
            agent_steps: buildStepsArray(stepsMap),
            plan: prev.plan ? {
              ...prev.plan,
              steps: prev.plan.steps.map((s, i) => i === data.index ? { ...s, status: 'running' } : s),
            } : null,
          }
        })
      },

      onStepDone: data => {
        setStreamingMsg(prev => {
          if (!prev) return prev
          const stepsMap = { ...(prev._stepsMap || {}) }
          if (stepsMap[data.index]) {
            stepsMap[data.index] = {
              ...stepsMap[data.index],
              status: 'done',
              content: data.content ?? stepsMap[data.index].content,
              metrics: data.metrics,
            }
          }
          return {
            ...prev,
            _stepsMap: stepsMap,
            agent_steps: buildStepsArray(stepsMap),
            plan: prev.plan ? {
              ...prev.plan,
              steps: prev.plan.steps.map((s, i) => i === data.index ? { ...s, status: 'done' } : s),
            } : null,
          }
        })
      },

      onDone: () => {
        stopStream()
        reloadChat()
        onChatsChanged?.()
      },

      onError: msg => {
        stopStream()
        setError(msg)
      },
    }
  }

  function beginStream() {
    setStreaming(true)
    setStreamingMsg({
      role: 'assistant',
      content: '',
      reasoning_content: '',
      plan: null,
      agent_steps: [],
      tool_calls: [],
      _stepsMap: {},
    })
  }

  function startResumeStream(msgId) {
    // Abort any existing stream first
    abortRef.current?.abort()
    beginStream()
    const ac = new AbortController()
    abortRef.current = ac
    resumeMessageStream(msgId, makeCallbacks(), ac.signal).catch(handleStreamErr)
  }

  /* ── effects ── */
  useEffect(() => () => { abortRef.current?.abort() }, [])

  useEffect(() => {
    if (!chatId) { setMessages([]); return }
    // Stale guard: abort previous stream + ignore stale fetches
    abortRef.current?.abort()
    let stale = false
    fetchChat(chatId).then(chat => {
      if (stale) return
      setMessages(enrichMessages(chat.messages || []))
      const last = chat.messages?.[chat.messages.length - 1]
      if (last?.role === 'assistant' && last?.status === 'generating') {
        startResumeStream(last.id)
      }
    }).catch(e => { if (!stale) setError(e.message) })
    return () => { stale = true; abortRef.current?.abort() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId])

  useEffect(() => {
    if (atBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingMsg])

  function onScroll() {
    const el = scrollRef.current
    if (!el) return
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  useEffect(() => { inputRef.current?.focus() }, [chatId])

  /* ── send ── */
  async function handleSend() {
    if (!input.trim() || !chatId || streaming) return
    const content = input.trim()
    setInput('')
    setError(null)
    if (inputRef.current) inputRef.current.style.height = 'auto'

    const tempId = Date.now()
    setMessages(prev => [...prev, { id: tempId, role: 'user', content, created_at: new Date().toISOString() }])
    beginStream()

    const ac = new AbortController()
    abortRef.current = ac

    const cbs = makeCallbacks({
      onUserMessage: msg => setMessages(prev => prev.map(m => m.id === tempId ? msg : m)),
      onAssistantMessageId: () => {},
    })

    try {
      await sendMessageStream(chatId, content, cbs, { useThinking, useAgent }, ac.signal)
    } catch (e) { handleStreamErr(e) }
  }

  function handleStop() {
    abortRef.current?.abort()
    stopStream()
    reloadChat()
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function onInputChange(e) {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }

  /* ── empty states ── */
  if (!chatId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-deep">
        <div className="text-center anim-fade">
          {workspaceId ? (
            <>
              <div className="text-4xl mb-3 opacity-15 text-accent">&#9670;</div>
              <p className="text-ink-muted text-[15px]">{t('chat.empty_chat')}</p>
            </>
          ) : (
            <>
              <div className="font-display text-3xl font-bold mb-2 tracking-tight">Atelier</div>
              <p className="text-ink-secondary text-[14px]">{t('chat.empty_workspace')}</p>
            </>
          )}
        </div>
      </div>
    )
  }

  /* ── render ── */
  return (
    <div className="flex-1 flex flex-col bg-deep min-w-0">
      {/* header bar — notes toggle only */}
      <div className="h-12 min-h-12 flex items-center justify-end px-4 border-b border-edge">
        <ToggleBtn
          active={showNotes}
          onClick={onToggleNotes}
          icon={showNotes ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
          label={t('notes.title')}
        />
      </div>

      {/* messages */}
      <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4 py-5">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && !streaming && (
            <p className="text-center text-ink-muted text-[13px] py-16 anim-fade">{t('chat.send_to_start')}</p>
          )}

          {messages.map(m => <MessageItem key={m.id} message={m} />)}

          {streaming && streamingMsg && (
            <MessageItem message={streamingMsg} isStreaming isThinking={isThinking} />
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* input */}
      <div className="border-t border-edge px-4 py-3">
        <div className="max-w-3xl mx-auto">
          {/* mode toggles */}
          <div className="flex items-center gap-2 mb-2">
            <ToggleBtn active={useThinking} onClick={() => setUseThinking(v => !v)} icon={<Brain size={13} />} label={t('chat.deep_thinking')} />
            <ToggleBtn active={useAgent} onClick={() => setUseAgent(v => !v)} icon={<Bot size={13} />} label="Agent" />
          </div>
          <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            placeholder={t('chat.placeholder')}
            rows={1}
            className="flex-1 bg-surface border border-edge rounded-xl px-4 py-3 text-[15px] text-ink resize-none focus:border-accent/60 transition-colors leading-relaxed"
            style={{ minHeight: 46, maxHeight: 140 }}
          />
          {streaming ? (
            <button onClick={handleStop} className="p-3 rounded-xl bg-cinnabar/90 text-ink hover:bg-cinnabar transition-colors shrink-0">
              <StopCircle size={18} />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-3 rounded-xl bg-accent text-deep hover:bg-accent-light disabled:opacity-25 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              <Send size={18} />
            </button>
          )}
          </div>
        </div>
        {error && <p className="max-w-3xl mx-auto mt-2 text-[12px] text-cinnabar">{error}</p>}
      </div>
    </div>
  )
}

/** Convert stepsMap { [index]: stepData } → sorted array for rendering */
function buildStepsArray(stepsMap) {
  return Object.keys(stepsMap)
    .map(Number)
    .sort((a, b) => a - b)
    .map(k => stepsMap[k])
}

function ToggleBtn({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[13px] font-medium transition-colors
        ${active ? 'bg-accent-dim text-accent' : 'text-ink-muted hover:text-ink hover:bg-hover'}`}
    >
      {icon}
      {label}
    </button>
  )
}
