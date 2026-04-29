import { request } from './client'

export function createChat(workspaceId) {
    return request(`/api/workspaces/${workspaceId}/chats`, { method: 'POST' })
}

export function fetchChats(workspaceId) {
    return request(`/api/workspaces/${workspaceId}/chats`)
}

export function fetchChat(chatId) {
    return request(`/api/chats/${chatId}`)
}

export function deleteChat(chatId) {
    return request(`/api/chats/${chatId}`, { method: 'DELETE' })
}

export function sendMessage(chatId, content) {
    return request(`/api/chats/${chatId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
    })
}

/**
 * 解析 SSE 流。
 * 带 step_index 的事件 (chunk, tool_call, tool_result, content_to_thinking)
 * 回调签名: callback(data, stepIndex)，stepIndex 可能为 undefined。
 */
async function parseSSEStream(response, callbacks, signal) {
    const {
        onUserMessage, onChunk, onReasoningChunk, onDone, onError,
        onAssistantMessageId, onToolCall, onToolResult,
        onContentToThinking, onPlan, onStepStart, onStepDone,
    } = callbacks

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    if (signal) {
        signal.addEventListener('abort', () => reader.cancel(), { once: true })
    }

    try {
        while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })

            const lines = buffer.split('\n')
            buffer = lines.pop()

            for (const line of lines) {
                if (!line.trim()) continue
                let msg
                try {
                    msg = JSON.parse(line)
                } catch {
                    onError?.(`数据解析错误`)
                    continue
                }

                const si = msg.step_index  // may be undefined

                if (msg.type === 'user_message') {
                    onUserMessage?.(msg.data)
                } else if (msg.type === 'assistant_message_id') {
                    onAssistantMessageId?.(msg.data)
                } else if (msg.type === 'reasoning_chunk') {
                    onReasoningChunk?.(msg.data, si)
                } else if (msg.type === 'chunk') {
                    onChunk?.(msg.data, si)
                } else if (msg.type === 'content_to_thinking') {
                    onContentToThinking?.(msg.data, si)
                } else if (msg.type === 'tool_call') {
                    onToolCall?.(msg.data, si)
                } else if (msg.type === 'tool_result') {
                    onToolResult?.(msg.data, si)
                } else if (msg.type === 'plan') {
                    onPlan?.(msg.data)
                } else if (msg.type === 'step_start') {
                    onStepStart?.(msg.data)
                } else if (msg.type === 'step_done') {
                    onStepDone?.(msg.data)
                } else if (msg.type === 'done') {
                    onDone?.(msg.data)
                } else if (msg.type === 'error' || msg.error) {
                    onError?.(msg.data || msg.error)
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') throw err
        onError?.(`流式传输异常: ${err.message}`)
    }
}

export async function sendMessageStream(chatId, content, callbacks, { useThinking = false, useAgent = false } = {}, signal) {
    const response = await fetch(`/api/chats/${chatId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, use_thinking: useThinking, use_agent: useAgent }),
        signal,
    })

    if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `请求失败: ${response.status}`)
    }

    await parseSSEStream(response, callbacks, signal)
}

export async function resumeMessageStream(messageId, callbacks, signal) {
    const response = await fetch(`/api/messages/${messageId}/stream`, { signal })

    if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `请求失败: ${response.status}`)
    }

    await parseSSEStream(response, callbacks, signal)
}
