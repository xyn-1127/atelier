import { request } from './client'

export function fetchFiles(workspaceId) {
    return request(`/api/workspaces/${workspaceId}/files`)
}

export function fetchFileContent(fileId) {
    return request(`/api/files/${fileId}/content`)
}

export function buildIndex(workspaceId) {
    return request(`/api/workspaces/${workspaceId}/index`, { method: 'POST' })
}

