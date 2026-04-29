export async function request(path, options = {}) {
    const response = await fetch(path, {
        headers: {
            'Content-Type': 'application/json',
        },
        ...options,
    })

    if (response.status === 204) {
        return null
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || `请求失败: ${response.status}`)
    }

    return response.json()
}