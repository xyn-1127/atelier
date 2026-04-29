import { request } from './client'

export function fetchNotes(workspaceId) {
    return request(`/api/workspaces/${workspaceId}/notes`)
}

export function createNote(workspaceId, data) {
    return request(`/api/workspaces/${workspaceId}/notes`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

export function updateNote(noteId, data) {
    return request(`/api/notes/${noteId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    })
}

export function deleteNote(noteId) {
    return request(`/api/notes/${noteId}`, { method: 'DELETE' })
}
