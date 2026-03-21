import React, { createContext, useContext, useState, useEffect } from 'react'

const PipelineContext = createContext(null)

const STORAGE_KEY = 'veritas_session'

// What we persist across refresh — only lightweight state, not the full report
function loadPersistedState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Only restore if it was stored recently (within 2 hours)
    if (Date.now() - (parsed.savedAt || 0) > 2 * 60 * 60 * 1000) {
      sessionStorage.removeItem(STORAGE_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

function persistState(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state, savedAt: Date.now() }))
  } catch {
    // sessionStorage not available (private mode etc) — silent fail
  }
}

function clearPersistedState() {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch {}
}

export function PipelineProvider({ children }) {
  const persisted = loadPersistedState()

  const [sessionId, setSessionId] = useState(persisted?.sessionId || null)
  const [inputText, setInputText] = useState(persisted?.inputText || '')
  const [inputMeta, setInputMeta] = useState(persisted?.inputMeta || null)
  const [report,    setReport]    = useState(null)  // never persisted — fetched fresh
  const [page,      setPage]      = useState(() => {
    // On refresh: if we had a completed session, go to report page (will fetch)
    // If we had an in-progress session, go back to pipeline (will reconnect)
    if (persisted?.page === 'report' && persisted?.sessionId) return 'report'
    if (persisted?.page === 'pipeline' && persisted?.sessionId) return 'pipeline'
    return 'landing'
  })

  // Persist lightweight state whenever it changes
  useEffect(() => {
    if (sessionId) {
      persistState({ sessionId, inputText, inputMeta, page })
    }
  }, [sessionId, inputText, inputMeta, page])

  const reset = () => {
    setSessionId(null)
    setInputText('')
    setInputMeta(null)
    setReport(null)
    setPage('input')
    clearPersistedState()
  }

  return (
    <PipelineContext.Provider value={{
      sessionId, setSessionId,
      inputText, setInputText,
      inputMeta, setInputMeta,
      report, setReport,
      page, setPage,
      reset,
    }}>
      {children}
    </PipelineContext.Provider>
  )
}

export function usePipelineContext() {
  const ctx = useContext(PipelineContext)
  if (!ctx) throw new Error('usePipelineContext must be inside PipelineProvider')
  return ctx
}
