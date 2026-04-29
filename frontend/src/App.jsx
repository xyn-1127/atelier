import { useState, useEffect, useCallback } from 'react'
import { fetchWorkspaces, createWorkspace as apiCreateWs, deleteWorkspace as apiDeleteWs } from './api/workspace'
import { fetchChats, createChat as apiCreateChat, deleteChat as apiDeleteChat } from './api/chat'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import NotesPanel from './components/NotesPanel'
import CreateWorkspaceModal from './components/CreateWorkspaceModal'

export default function App() {
  const [workspaces, setWorkspaces] = useState([])
  const [activeWsId, setActiveWsId] = useState(null)
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [showNotes, setShowNotes] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('atelier-theme') || 'dark')
  const [notesKey, setNotesKey] = useState(0)

  const activeWs = workspaces.find(w => w.id === activeWsId) || null

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('atelier-theme', theme)
  }, [theme])

  /* ── data loading ── */
  useEffect(() => {
    fetchWorkspaces().then(setWorkspaces).catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (activeWsId) {
      fetchChats(activeWsId).then(setChats).catch(e => setError(e.message))
    }
  }, [activeWsId])

  const refreshChats = useCallback(() => {
    if (activeWsId) fetchChats(activeWsId).then(setChats).catch(() => {})
  }, [activeWsId])

  /* ── workspace actions ── */
  function selectWorkspace(id) {
    setActiveWsId(id)
    setActiveChatId(null)
    setChats([])
  }

  async function handleCreateWs(data) {
    const ws = await apiCreateWs(data)
    setWorkspaces(prev => [...prev, ws])
    setActiveWsId(ws.id)
    setShowCreateModal(false)
  }

  async function handleDeleteWs(id) {
    try {
      await apiDeleteWs(id)
      setWorkspaces(prev => prev.filter(w => w.id !== id))
      if (activeWsId === id) { setActiveWsId(null); setActiveChatId(null); setChats([]) }
    } catch (e) { setError(e.message) }
  }

  /* ── chat actions ── */
  async function handleCreateChat() {
    if (!activeWsId) return
    try {
      const chat = await apiCreateChat(activeWsId)
      setChats(prev => [chat, ...prev])
      setActiveChatId(chat.id)
    } catch (e) { setError(e.message) }
  }

  async function handleDeleteChat(id) {
    try {
      await apiDeleteChat(id)
      setChats(prev => prev.filter(c => c.id !== id))
      if (activeChatId === id) setActiveChatId(null)
    } catch (e) { setError(e.message) }
  }

  /* ── render ── */
  return (
    <div className="flex h-screen bg-deep text-ink overflow-hidden">
      <Sidebar
        workspaces={workspaces}
        activeWs={activeWs}
        chats={chats}
        activeChatId={activeChatId}
        onSelectWs={selectWorkspace}
        onSelectChat={setActiveChatId}
        onCreateWs={() => setShowCreateModal(true)}
        onCreateChat={handleCreateChat}
        onDeleteWs={handleDeleteWs}
        onDeleteChat={handleDeleteChat}
        onBack={() => { setActiveWsId(null); setActiveChatId(null); setChats([]) }}
        theme={theme}
        onToggleTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
      />

      <ChatView
        key={activeChatId}
        chatId={activeChatId}
        workspaceId={activeWsId}
        showNotes={showNotes}
        onToggleNotes={() => setShowNotes(v => !v)}
        onChatsChanged={() => { refreshChats(); setNotesKey(k => k + 1) }}
      />

      {showNotes && activeWsId && (
        <NotesPanel workspaceId={activeWsId} onClose={() => setShowNotes(false)} refreshKey={notesKey} />
      )}

      {showCreateModal && (
        <CreateWorkspaceModal
          onSubmit={handleCreateWs}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {error && (
        <div className="fixed bottom-4 right-4 bg-cinnabar/90 text-ink px-4 py-2.5 rounded-xl shadow-lg anim-fade z-50 text-sm flex items-center gap-3">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="opacity-70 hover:opacity-100">✕</button>
        </div>
      )}
    </div>
  )
}
