import { useState, useEffect, useRef, useCallback } from 'react'

export function usePipeline(sessionId) {
  const [stage, setStage]             = useState('idle')
  const [claims, setClaims]           = useState([])
  const [claimUpdates, setClaimUpdates] = useState({})
  const [report, setReport]           = useState(null)
  const [error, setError]             = useState(null)
  const [progressPct, setProgressPct] = useState(0)
  const [searchFeeds, setSearchFeeds] = useState({})

  const esRef          = useRef(null)
  const reconnectRef   = useRef(0)
  const mountedRef     = useRef(true)
  const lastEventIdRef = useRef(0)          // track for SSE Last-Event-ID replay
  const isFinishedRef  = useRef(false)      // fix: ref instead of stale closure

  const handleEvent = useCallback((event) => {
    if (!mountedRef.current) return
    const s = event.stage

    if (s === 'heartbeat') return

    if (s === 'extracting') {
      setStage('extracting')
      setProgressPct(10)
    }
    if (s === 'extraction_complete') {
      setClaims(event.claims || [])
      setStage('retrieving')
      setProgressPct(25)
    }
    if (s === 'evidence_retrieved') {
      const { claim_id, source_count, queries } = event
      setClaimUpdates(prev => ({
        ...prev,
        [claim_id]: { ...prev[claim_id], source_count, status: 'verifying' }
      }))
      if (queries) setSearchFeeds(prev => ({ ...prev, [claim_id]: queries }))
      setProgressPct(prev => Math.min(60, prev + 2))
    }
    if (s === 'verifying') {
      setStage('verifying')
    }
    if (s === 'verdict_ready') {
      const { claim_id, verdict, confidence, conflict_flag } = event
      setClaimUpdates(prev => ({
        ...prev,
        [claim_id]: { ...prev[claim_id], verdict, confidence, conflict_flag, status: 'done' }
      }))
      setProgressPct(prev => Math.min(85, prev + 3))
    }
    if (s === 'analyzing') {
      setStage('analyzing')
      setProgressPct(90)
    }
    if (s === 'report_complete') {
      setReport(event.report)
      setStage('complete')
      setProgressPct(100)
      isFinishedRef.current = true
      esRef.current?.close()
    }
    if (s === 'error') {
      setError(event.message || 'An error occurred')
      setStage('error')
      isFinishedRef.current = true
      esRef.current?.close()
    }
  }, [])

  const connect = useCallback(() => {
    if (!sessionId || !mountedRef.current || isFinishedRef.current) return

    // Include Last-Event-ID so server can replay missed events
    const url = `/api/stream/${sessionId}?lastEventId=${lastEventIdRef.current}`
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (e) => {
      // Track Last-Event-ID from server
      if (e.lastEventId) {
        lastEventIdRef.current = parseInt(e.lastEventId, 10) || lastEventIdRef.current
      }
      let event
      try { event = JSON.parse(e.data) } catch { return }
      handleEvent(event)
    }

    es.onerror = () => {
      if (!mountedRef.current) return
      es.close()
      // Only reconnect if pipeline is still running (use ref — not stale closure)
      if (!isFinishedRef.current && reconnectRef.current < 5) {
        reconnectRef.current += 1
        const delay = Math.min(1000 * reconnectRef.current, 8000) // capped backoff
        setTimeout(connect, delay)
      }
    }
  }, [sessionId, handleEvent])

  useEffect(() => {
    mountedRef.current = true
    isFinishedRef.current = false
    if (sessionId) {
      reconnectRef.current = 0
      lastEventIdRef.current = 0
      connect()
    }
    return () => {
      mountedRef.current = false
      esRef.current?.close()
    }
  }, [sessionId, connect])

  return { stage, claims, claimUpdates, searchFeeds, report, error, progressPct }
}
