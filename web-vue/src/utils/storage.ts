/**
 * 本地存储封装
 */

const PREFIX = 'douyin_'

export const storage = {
  get<T = any>(key: string, defaultValue?: T): T | null {
    const value = localStorage.getItem(PREFIX + key)
    if (value === null) return defaultValue ?? null
    try {
      return JSON.parse(value) as T
    } catch {
      return value as unknown as T
    }
  },

  set(key: string, value: any): void {
    const serialized = typeof value === 'string' ? value : JSON.stringify(value)
    localStorage.setItem(PREFIX + key, serialized)
  },

  remove(key: string): void {
    localStorage.removeItem(PREFIX + key)
  },

  clear(): void {
    const keys = Object.keys(localStorage)
    keys.forEach(key => {
      if (key.startsWith(PREFIX)) {
        localStorage.removeItem(key)
      }
    })
  }
}

export const sessionStorage_ = {
  get<T = any>(key: string, defaultValue?: T): T | null {
    const value = sessionStorage.getItem(PREFIX + key)
    if (value === null) return defaultValue ?? null
    try {
      return JSON.parse(value) as T
    } catch {
      return value as unknown as T
    }
  },

  set(key: string, value: any): void {
    const serialized = typeof value === 'string' ? value : JSON.stringify(value)
    sessionStorage.setItem(PREFIX + key, serialized)
  },

  remove(key: string): void {
    sessionStorage.removeItem(PREFIX + key)
  },

  clear(): void {
    sessionStorage.clear()
  }
}
