import { useState } from 'react'
import { FolderOpen, MessageSquare, Plus, Trash2, ArrowLeft, Sparkles, Sun, Moon } from 'lucide-react'

export default function Sidebar({
  workspaces, activeWs, chats, activeChatId,
  onSelectWs, onSelectChat, onCreateWs, onCreateChat,
  onDeleteWs, onDeleteChat, onBack, theme, onToggleTheme,
}) {
  const [hoverWs, setHoverWs] = useState(null)
  const [hoverChat, setHoverChat] = useState(null)

  return (
    <aside className="w-[260px] min-w-[260px] h-full bg-base border-r border-edge flex flex-col select-none">
      {/* ── brand ── */}
      <div className="px-5 pt-5 pb-4">
        <h1 className="font-display text-[1.15rem] font-bold tracking-tight flex items-center gap-2 text-ink">
          <Sparkles size={17} className="text-accent" />
          Atelier
        </h1>
      </div>

      {/* ── content ── */}
      <div className="flex-1 overflow-y-auto px-3 pb-2">
        {activeWs ? (
          /* ── chat list mode ── */
          <div className="anim-left">
            <button
              onClick={onBack}
              className="w-full flex items-center gap-2 px-2 py-2 mb-1 rounded-lg text-ink-secondary hover:text-ink hover:bg-hover transition-colors"
            >
              <ArrowLeft size={14} className="shrink-0" />
              <div className="text-left min-w-0">
                <div className="text-ink font-medium truncate text-[14px]">{activeWs.name}</div>
                <div className="text-[12px] text-ink-muted truncate">{activeWs.path}</div>
              </div>
            </button>

            <div className="border-t border-edge my-2" />

            <div className="px-2 py-1 mb-1">
              <span className="text-[12px] font-medium text-ink-muted uppercase tracking-wider">对话</span>
            </div>

            {chats.map(c => (
              <div
                key={c.id}
                className={`group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors mb-px
                  ${activeChatId === c.id ? 'bg-accent-dim text-accent' : 'hover:bg-hover text-ink-secondary hover:text-ink'}`}
                onClick={() => onSelectChat(c.id)}
                onMouseEnter={() => setHoverChat(c.id)}
                onMouseLeave={() => setHoverChat(null)}
              >
                <MessageSquare size={14} className="shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] truncate">{c.title || '新对话'}</div>
                  <div className="text-[12px] text-ink-muted">{new Date(c.created_at).toLocaleDateString('zh-CN')}</div>
                </div>
                {hoverChat === c.id && (
                  <button
                    onClick={e => { e.stopPropagation(); onDeleteChat(c.id) }}
                    className="text-ink-muted hover:text-cinnabar transition-colors p-0.5"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}

            {chats.length === 0 && (
              <p className="px-2 py-8 text-center text-ink-muted text-[14px]">暂无对话</p>
            )}

            <button
              onClick={onCreateChat}
              className="w-full flex items-center gap-2 px-2 py-2 mt-1 rounded-lg text-ink-muted hover:text-accent hover:bg-accent-dim transition-colors text-[14px]"
            >
              <Plus size={14} />
              新建对话
            </button>
          </div>
        ) : (
          /* ── workspace list mode ── */
          <div className="anim-fade">
            <div className="px-2 py-1 mb-1">
              <span className="text-[12px] font-medium text-ink-muted uppercase tracking-wider">工作区</span>
            </div>

            {workspaces.map(ws => (
              <div
                key={ws.id}
                className="group flex items-center gap-2.5 px-2 py-2.5 rounded-lg cursor-pointer hover:bg-hover transition-colors mb-px"
                onClick={() => onSelectWs(ws.id)}
                onMouseEnter={() => setHoverWs(ws.id)}
                onMouseLeave={() => setHoverWs(null)}
              >
                <FolderOpen size={16} className="text-accent shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] text-ink truncate">{ws.name}</div>
                  <div className="text-[12px] text-ink-muted truncate">{ws.path}</div>
                </div>
                {hoverWs === ws.id && (
                  <button
                    onClick={e => { e.stopPropagation(); onDeleteWs(ws.id) }}
                    className="text-ink-muted hover:text-cinnabar transition-colors p-0.5"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}

            {workspaces.length === 0 && (
              <p className="px-2 py-8 text-center text-ink-muted text-[14px]">还没有工作区</p>
            )}

            <button
              onClick={onCreateWs}
              className="w-full flex items-center gap-2 px-2 py-2 mt-1 rounded-lg text-ink-muted hover:text-accent hover:bg-accent-dim transition-colors text-[14px]"
            >
              <Plus size={14} />
              新建工作区
            </button>
          </div>
        )}
      </div>

      {/* ── footer ── */}
      <div className="px-5 py-3 border-t border-edge flex items-center justify-between">
        <span className="text-[12px] text-ink-muted">v0.1 · local-first</span>
        <button
          onClick={onToggleTheme}
          className="p-1.5 rounded-lg text-ink-muted hover:text-accent hover:bg-accent-dim transition-colors"
          title={theme === 'dark' ? '切换浅色模式' : '切换深色模式'}
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </aside>
  )
}
