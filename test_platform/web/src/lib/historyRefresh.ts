const listeners = new Set<() => void>()

export function subscribeHistoryRefresh(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function notifyHistoryRefresh(): void {
  listeners.forEach((listener) => {
    listener()
  })
}
