import { request } from './client'                                                                                                 
                
export function fetchHealth() {
return request('/health')
}

export function fetchSystemInfo() {                                                                                                
return request('/system')
}     