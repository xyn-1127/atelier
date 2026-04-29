import { useState, useEffect, useRef } from 'react'
import { fetchNotes, createNote, updateNote, deleteNote } from '../api/notes'
import { X, Plus, Trash2, Edit3, Check, FileText } from 'lucide-react'
import Markdown from './Markdown'
import { useLang } from '../i18n'

export default function NotesPanel({ workspaceId, onClose, refreshKey }) {
  const { t, lang } = useLang()
  const dateLocale = lang === 'zh' ? 'zh-CN' : 'en-GB'
  const [notes, setNotes] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ title: '', content: '' })
  const [error, setError] = useState(null)
  const titleRef = useRef(null)

  const activeNote = notes.find(n => n.id === activeId) || null

  useEffect(() => {
    fetchNotes(workspaceId).then(setNotes).catch(e => setError(e.message))
  }, [workspaceId, refreshKey])

  useEffect(() => { if (editing) titleRef.current?.focus() }, [editing])

  function select(note) { setActiveId(note.id); setEditing(false) }

  function startEdit(note) {
    setForm({ title: note?.title || '', content: note?.content || '' })
    setEditing(true)
  }

  async function handleCreate() {
    try {
      const n = await createNote(workspaceId, { title: t('notes.new_default'), content: '' })
      setNotes(prev => [n, ...prev])
      setActiveId(n.id)
      startEdit(n)
    } catch (e) { setError(e.message) }
  }

  async function handleSave() {
    if (!activeId) return
    try {
      const updated = await updateNote(activeId, form)
      setNotes(prev => prev.map(n => n.id === activeId ? updated : n))
      setEditing(false)
    } catch (e) { setError(e.message) }
  }

  async function handleDelete(id) {
    try {
      await deleteNote(id)
      setNotes(prev => prev.filter(n => n.id !== id))
      if (activeId === id) { setActiveId(null); setEditing(false) }
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="w-[340px] min-w-[340px] h-full border-l border-edge bg-base flex flex-col anim-right select-none">
      {/* header */}
      <div className="h-12 min-h-12 flex items-center justify-between px-4 border-b border-edge">
        <span className="text-[14px] font-medium text-ink-secondary">{t('notes.title')}</span>
        <button onClick={onClose} className="text-ink-muted hover:text-ink transition-colors p-0.5">
          <X size={16} />
        </button>
      </div>

      {activeNote && !editing ? (
        /* ── view mode ── */
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-edge">
            <h3 className="text-[15px] font-medium truncate flex-1">{activeNote.title}</h3>
            <div className="flex items-center gap-1 ml-2 shrink-0">
              <button onClick={() => startEdit(activeNote)} className="p-1.5 rounded-md text-ink-muted hover:text-accent hover:bg-accent-dim transition-colors">
                <Edit3 size={13} />
              </button>
              <button onClick={() => setActiveId(null)} className="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-hover transition-colors">
                <X size={13} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-3">
            <div className="text-[14px] text-ink-secondary leading-relaxed">
              {activeNote.content
                ? <Markdown>{activeNote.content}</Markdown>
                : <span className="text-ink-muted">{t('notes.empty_placeholder')}</span>}
            </div>
          </div>
        </div>
      ) : activeNote && editing ? (
        /* ── edit mode ── */
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-edge">
            <input
              ref={titleRef}
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full bg-transparent text-[14px] font-medium text-ink border-none"
              placeholder={t('notes.title_placeholder')}
            />
          </div>
          <textarea
            value={form.content}
            onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
            className="flex-1 bg-transparent text-[13px] text-ink-secondary px-4 py-3 resize-none leading-relaxed"
            placeholder={t('notes.content_placeholder')}
          />
          <div className="flex items-center gap-2 px-4 py-3 border-t border-edge">
            <button
              onClick={handleSave}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-deep text-[12px] font-medium hover:bg-accent-light transition-colors"
            >
              <Check size={12} /> {t('common.save')}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1.5 rounded-lg text-ink-muted text-[12px] hover:text-ink hover:bg-hover transition-colors"
            >
              {t('common.cancel')}
            </button>
          </div>
          {error && <p className="px-4 pb-2 text-[11px] text-cinnabar">{error}</p>}
        </div>
      ) : (
        /* ── list mode ── */
        <div className="flex-1 overflow-y-auto">
          <div className="px-3 py-2">
            {notes.map(n => (
              <div
                key={n.id}
                className="group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer hover:bg-hover transition-colors mb-px"
                onClick={() => select(n)}
              >
                <FileText size={14} className="text-ink-muted shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] text-ink truncate">{n.title}</div>
                  <div className="text-[12px] text-ink-muted">{new Date(n.updated_at).toLocaleDateString(dateLocale)}</div>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); handleDelete(n.id) }}
                  className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-cinnabar transition-all p-0.5"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
            {notes.length === 0 && (
              <p className="py-10 text-center text-ink-muted text-[14px]">{t('notes.empty')}</p>
            )}
          </div>
        </div>
      )}

      {/* new note btn (list view only) */}
      {!activeNote && (
        <div className="px-3 py-3 border-t border-edge">
          <button
            onClick={handleCreate}
            className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-ink-muted hover:text-accent hover:bg-accent-dim transition-colors text-[14px]"
          >
            <Plus size={14} /> {t('notes.new')}
          </button>
        </div>
      )}
    </div>
  )
}
