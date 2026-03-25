import { createJSONStorage, type PersistStorage } from 'zustand/middleware'

type StorageLike = {
  getItem: (name: string) => string | null | Promise<string | null>
  setItem: (name: string, value: string) => unknown
  removeItem: (name: string) => unknown
}

type WindowLike = {
  localStorage?: StorageLike
}

function isQuotaExceededError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }

  const name = String((error as { name?: unknown }).name || '')
  const message = String((error as { message?: unknown }).message || '')
  return name === 'QuotaExceededError' || /exceeded the quota/i.test(message)
}

function hasStorageApi(storage: unknown): storage is StorageLike {
  return !!storage
    && typeof storage === 'object'
    && typeof (storage as StorageLike).getItem === 'function'
    && typeof (storage as StorageLike).setItem === 'function'
    && typeof (storage as StorageLike).removeItem === 'function'
}

/**
 * 仅在浏览器 localStorage API 完整可用时启用持久化，避免服务端运行时误触发存储实现。
 */
export function resolveAppStoreStorage<State>(
  targetWindow: WindowLike | undefined = typeof window === 'undefined' ? undefined : window
): PersistStorage<State, unknown> | undefined {
  const storage = targetWindow?.localStorage

  if (!hasStorageApi(storage)) {
    return undefined
  }

  const safeStorage: StorageLike = {
    getItem: (name) => storage.getItem(name),
    setItem: (name, value) => {
      try {
        storage.setItem(name, value)
      } catch (error) {
        if (!isQuotaExceededError(error)) {
          throw error
        }

        try {
          storage.removeItem(name)
        } catch {
          // 忽略清理阶段异常，保证页面不被持久化失败打断。
        }
      }
    },
    removeItem: (name) => storage.removeItem(name),
  }

  return createJSONStorage<State>(() => safeStorage)
}
