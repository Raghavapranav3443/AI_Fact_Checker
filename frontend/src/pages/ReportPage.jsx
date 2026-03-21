import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { usePipelineContext } from '../context/PipelineContext'
import TrustScore from '../components/TrustScore'
import TextAnnotator from '../components/TextAnnotator'
import ClaimDetail from '../components/ClaimDetail'
import ConflictPanel from '../components/ConflictPanel'
import AIDetectionPanel from '../components/AIDetectionPanel'
import MediaPanel from '../components/MediaPanel'
import './ReportPage.css'

export default function ReportPage() {
  const { report, setReport, sessionId, reset } = usePipelineContext()
  const [selectedClaimId, setSelectedClaimId] = useState(null)
  const [activeTab, setActiveTab] = useState('claims')
  const [fetchError, setFetchError] = useState(null)
  const [fetching, setFetching] = useState(false)

  // If report is null but we have a sessionId (page refresh case), fetch it
  useEffect(() => {
    if (!report && sessionId && !fetching) {
      setFetching(true)
      axios.get(`/api/report/${sessionId}`)
        .then(res => {
          // Re-attach input_text from context if available (stripped from API response)
          setReport(res.data)
        })
        .catch(err => {
          if (err.response?.status === 202) {
            // Still running — redirect back to pipeline page
            // (handled by App.jsx watching this)
          } else {
            setFetchError('Could not load report. The session may have expired.')
          }
        })
        .finally(() => setFetching(false))
    }
  }, [report, sessionId])

  if (fetching) {
    return (
      <div className="report-loading">
        <div className="rl-spinner" />
        <p>Loading report...</p>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="report-loading">
        <p className="rl-error">{fetchError}</p>
        <button className="rl-back" onClick={reset}>← Start new analysis</button>
      </div>
    )
  }

  if (!report) return null

  const selectedClaim = report.claims?.find(c => c.claim_id === selectedClaimId)
  const hasConflicts  = report.conflicts?.length > 0
  const hasMedia      = report.media_detection?.length > 0
  const hasAI         = !!report.ai_text_detection

  const tabs = [
    { key: 'claims',    label: 'Claims',       count: report.claims?.length || 0 },
    { key: 'conflicts', label: 'Conflicts',    count: report.conflicts?.length || 0, alert: hasConflicts },
    { key: 'ai',        label: 'AI Detection', count: null, show: hasAI },
    { key: 'media',     label: 'Media',        count: report.media_detection?.length || 0, show: hasMedia },
  ].filter(t => t.show !== false)

  return (
    <div className="report-page">
      <header className="report-header">
        <div className="rh-left">
          <span className="report-logo">
            <span className="rl-v">V</span><span className="rl-rest">ERITAS</span>
          </span>
          <span className="report-badge mono">Trust Report</span>
        </div>
        <div className="rh-right no-print">
          <button className="export-pdf-btn" onClick={() => window.print()} style={{ marginRight: '16px', background: 'transparent', border: '1px solid var(--accent)', color: 'var(--accent)', padding: '6px 16px', borderRadius: '24px', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>Export PDF</button>
          <span className="report-time mono">
            {report.processed_at ? new Date(report.processed_at).toLocaleTimeString() : ''}
          </span>
          <button className="new-analysis-btn" onClick={reset}>+ New analysis</button>
        </div>
      </header>

      {report.opinion_flag && (
        <div className="global-opinion-warning" style={{ background: 'rgba(245,166,35,0.15)', color: '#f5a623', padding: '12px', textAlign: 'center', borderBottom: '1px solid rgba(245,166,35,0.3)' }}>
          <strong>⚠ Opinion Content Detected:</strong> This text is primarily opinion. Extracted claims reflect stated facts within it, not the opinions themselves.
        </div>
      )}

      <div className="report-body">
        <div className="report-left">
          <TrustScore score={report.overall_trust_score || 0} breakdown={report.claim_breakdown || {}} />

          <div className="tab-bar">
            {tabs.map(t => (
              <button
                key={t.key}
                className={`tab-btn ${activeTab === t.key ? 'active' : ''} ${t.alert ? 'alert' : ''}`}
                onClick={() => setActiveTab(t.key)}
              >
                {t.label}
                {t.count !== null && t.count > 0 && <span className="tab-count">{t.count}</span>}
              </button>
            ))}
          </div>

          {activeTab === 'claims' && (
            <div className="tab-content animate-in">
              <TextAnnotator
                text={report.input_text || ''}
                claims={report.claims || []}
                selectedClaimId={selectedClaimId}
                onSelectClaim={setSelectedClaimId}
              />
            </div>
          )}
          {activeTab === 'conflicts' && (
            <div className="tab-content animate-in">
              <ConflictPanel conflicts={report.conflicts || []} />
            </div>
          )}
          {activeTab === 'ai' && hasAI && (
            <div className="tab-content animate-in">
              <AIDetectionPanel data={report.ai_text_detection} />
            </div>
          )}
          {activeTab === 'media' && hasMedia && (
            <div className="tab-content animate-in">
              <MediaPanel results={report.media_detection} />
            </div>
          )}
        </div>

        <div className={`report-right ${selectedClaim ? 'has-claim' : ''}`}>
          {selectedClaim ? (
            <ClaimDetail claim={selectedClaim} onClose={() => setSelectedClaimId(null)} />
          ) : (
            <div className="detail-empty">
              <div className="de-icon">⊛</div>
              <p>Select a highlighted claim in the text to see full verification details</p>
            </div>
          )}
        </div>
      </div>

      {/* Print-only Full Report */}
      <div className="print-only-report" style={{ display: 'none', padding: '20px' }}>
        <h2 style={{ marginBottom: '20px', borderBottom: '1px solid #ccc', paddingBottom: '10px' }}>Veritas Full Evaluation Report</h2>
        <div style={{ marginBottom: '30px' }}>
          <TrustScore score={report.overall_trust_score || 0} breakdown={report.claim_breakdown || {}} />
        </div>
        
        {report.conflicts?.length > 0 && (
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ marginBottom: '16px' }}>Conflicts Detected</h3>
            <ConflictPanel conflicts={report.conflicts} />
          </div>
        )}

        <h3 style={{ marginBottom: '16px' }}>Evaluated Claims ({report.claims?.length || 0})</h3>
        <div style={{ display: 'block' }}>
          {report.claims?.map(claim => (
            <div key={claim.claim_id} style={{ pageBreakInside: 'avoid', breakInside: 'avoid', marginBottom: '24px' }}>
              <ClaimDetail claim={claim} onClose={() => {}} isPrintMode={true} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
