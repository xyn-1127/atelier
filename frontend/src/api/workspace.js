import { request } from './client'

export function fetchWorkspaces() {
return request('/api/workspaces')
}

export function createWorkspace(data) {
return request('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify(data),
})
}

export function deleteWorkspace(id) {
return request(`/api/workspaces/${id}`, {
    method: 'DELETE',
})
}

export function scanWorkspace(id) {
return request(`/api/workspaces/${id}/scan`, {
    method: 'POST',
})
}