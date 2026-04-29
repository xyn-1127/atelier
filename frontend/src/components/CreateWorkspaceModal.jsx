import { useState, useEffect } from 'react'
import { request } from '../api/client'
import { X, FolderOpen, ArrowUp } from 'lucide-react'

export default function CreateWorkspaceModal({ onSubmit, onClose }) {
  const [name, setName] = useState('')
  const [path, setPath] = useState('')
  const [showBrowser, setShowBrowser] = useState(false)
  const [browsePath, setBrowsePath] = useState('')
  const [dirs, setDirs] = useState([])
  const [parentPath, setParentPath] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  function browse(p) {
    request(`/api/browse?path=${encodeURIComponent(p)}`).then(d => {
      setBrowsePath(d.current)
      setDirs(d.dirs || [])
      setParentPath(d.parent)
      setError(d.error || null)
    }).catch(e => setError(e.message))
  }

  useEffect(() => { if (showBrowser) browse('~') }, [showBrowser])

  function pick(p) { setPath(p); setShowBrowser(false) }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim() || !path.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({ name: name.trim(), path: path.trim() })
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-base border border-edge rounded-2xl w-full max-w-md mx-4 shadow-2xl anim-fade"
        onClick={e => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-edge">
          <h2 className="text-[15px] font-medium">新建工作区</h2>
          <button onClick={onClose} className="text-ink-muted hover:text-ink transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          {/* name */}
          <div>
            <label className="block text-[11px] text-ink-muted mb-1.5 uppercase tracking-wider font-medium">名称</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="我的项目"
              className="w-full bg-surface border border-edge rounded-lg px-3 py-2.5 text-[13px] text-ink focus:border-accent/60 transition-colors"
              autoFocus
            />
          </div>

          {/* path */}
          <div>
            <label className="block text-[11px] text-ink-muted mb-1.5 uppercase tracking-wider font-medium">路径</label>
            <div className="flex gap-2">
              <input
                value={path}
                onChange={e => setPath(e.target.value)}
                placeholder="/home/user/project"
                className="flex-1 bg-surface border border-edge rounded-lg px-3 py-2.5 text-[12px] text-ink font-mono focus:border-accent/60 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowBrowser(v => !v)}
                className={`px-3 rounded-lg border transition-colors
                  ${showBrowser ? 'border-accent/50 bg-accent-dim text-accent' : 'border-edge text-ink-muted hover:text-ink hover:border-edge-light'}`}
              >
                <FolderOpen size={16} />
              </button>
            </div>
          </div>

          {/* directory browser */}
          {showBrowser && (
            <div className="border border-edge rounded-xl overflow-hidden bg-surface anim-fade">
              <div className="flex items-center gap-2 px-3 py-2 bg-elevated text-[11px] text-ink-muted border-b border-edge">
                {parentPath && (
                  <button type="button" onClick={() => browse(parentPath)} className="text-ink-secondary hover:text-ink transition-colors">
                    <ArrowUp size={14} />
                  </button>
                )}
                <span className="font-mono truncate flex-1">{browsePath}</span>
                <button type="button" onClick={() => pick(browsePath)} className="text-accent hover:text-accent-light text-[11px] font-medium shrink-0">
                  选择此目录
                </button>
              </div>
              <div className="max-h-44 overflow-y-auto">
                {dirs.map(d => (
                  <div key={d.path} className="flex items-center gap-2 px-3 py-1.5 hover:bg-hover transition-colors text-[13px]">
                    <FolderOpen size={13} className="text-accent shrink-0" />
                    <span
                      className="flex-1 truncate text-ink-secondary hover:text-ink cursor-pointer"
                      onClick={() => browse(d.path)}
                    >
                      {d.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => pick(d.path)}
                      className="text-[11px] text-ink-muted hover:text-accent transition-colors shrink-0"
                    >
                      选择
                    </button>
                  </div>
                ))}
                {dirs.length === 0 && (
                  <p className="px-3 py-3 text-[12px] text-ink-muted text-center">空目录</p>
                )}
              </div>
            </div>
          )}

          {error && <p className="text-[12px] text-cinnabar">{error}</p>}

          {/* actions */}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-[13px] text-ink-muted hover:text-ink hover:bg-hover transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !path.trim() || submitting}
              className="px-5 py-2 rounded-lg text-[13px] bg-accent text-deep font-medium hover:bg-accent-light disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
