import React, { useEffect } from 'react'
import { usePipelineContext } from '../context/PipelineContext'
import { usePipeline } from '../hooks/usePipeline'
import StageIndicator from '../components/StageIndicator'
import LiveClaimCard from '../components/LiveClaimCard'
import './PipelinePage.css'

export default function PipelinePage() {
  const { sessionId, inputMeta, setReport, setPage, reset } = usePipelineContext()
  const { stage, claims, claimUpdates, searchFeeds, report, error, progressPct } = usePipeline(sessionId)

  // When pipeline completes, stash report and navigate
  useEffect(() => {
    if (report) {
      setReport(report)
      // Small delay so user sees the 100% state
      setTimeout(() => setPage('report'), 600)
    }
  }, [report])

  const stageLabels = {
    idle:       'Initialising...',
    extracting: 'Extracting claims',
    retrieving: 'Retrieving evidence',
    verifying:  'Verifying claims',
    analyzing:  'Analysing content',
    complete:   'Complete',
    error:      'Error',
  }

  return (
    <div className="pipeline-page">
      {/* Top bar */}
      <header className="pipeline-header">
        <div className="pipeline-logo">
          <span className="pl-v">V</span><span className="pl-rest">ERITAS</span>
        </div>
        <button className="cancel-btn" onClick={reset}>✕ Cancel</button>
      </header>

      {/* Progress rail */}
      <div className="progress-rail">
        <div className="progress-fill" style={{ width: `${progressPct}%` }} />
      </div>

      <main className="pipeline-main">
        {/* Stage indicator */}
        <StageIndicator currentStage={stage} />

        {/* Status line */}
        <div className="status-line">
          <span className={`status-dot ${stage !== 'complete' && stage !== 'error' ? 'pulsing' : ''}`} />
          <span className="status-label mono">
            {error ? error : stageLabels[stage] || stage}
          </span>
          {inputMeta && stage !== 'complete' && (
            <span className="eta mono">~{inputMeta.estimated_time_seconds}s</span>
          )}
        </div>

        {/* Error state */}
        {error && (
          <div className="pipeline-error animate-in">
            <span>⚠</span> {error}
            <button className="err-back-btn" onClick={reset}>← Start over</button>
          </div>
        )}

        {/* Claims grid */}
        {claims.length > 0 && (
          <div className="claims-section animate-in">
            <div className="claims-header">
              <span className="claims-title">
                <span className="mono accent">{claims.length}</span> claims extracted
              </span>
              <span className="claims-legend">
                {Object.entries(
                  Object.values(claimUpdates).reduce((acc, v) => {
                    if (v.verdict) acc[v.verdict] = (acc[v.verdict] || 0) + 1
                    return acc
                  }, {})
                ).map(([v, n]) => (
                  <span key={v} className={`legend-item verdict-${v}`}>
                    {n} {v.toLowerCase()}
                  </span>
                ))}
              </span>
            </div>

            <div className="claims-grid">
              {claims.map(claim => (
                <LiveClaimCard
                  key={claim.claim_id}
                  claim={claim}
                  update={claimUpdates[claim.claim_id]}
                  queries={searchFeeds[claim.claim_id]}
                />
              ))}
            </div>
          </div>
        )}

        {/* Empty state while waiting for extraction */}
        {claims.length === 0 && stage !== 'error' && (
          <div className="waiting-state">
            <div className="waiting-orbs">
              <div className="orb orb-1" /><div className="orb orb-2" /><div className="orb orb-3" />
            </div>
            <p className="waiting-text mono">Analysing text structure...</p>
          </div>
        )}
      </main>
    </div>
  )
}
