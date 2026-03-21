import React, { useState } from 'react'
import { getVerdict, claimTypeColor, confidenceColor } from '../utils'
import './ClaimDetail.css'

function SourceCard({ source, isCited }) {
  const tier = source.authority_score >= 1.0 ? 1 : source.authority_score >= 0.7 ? 2 : 3
  const tierColors = { 1: 'var(--true)', 2: 'var(--accent)', 3: 'var(--text-muted)' }
  return (
    <div className={`source-card ${isCited ? 'cited' : ''}`}>
      <div className="sc-header">
        <span className="sc-domain mono">{source.domain}</span>
        <span className="sc-tier mono" style={{ color: tierColors[tier] }}>T{tier}</span>
        {source.publish_date && <span className="sc-date">{source.publish_date.slice(0, 10)}</span>}
        {isCited && <span className="sc-cited-badge">cited</span>}
      </div>
      <p className="sc-title">{source.title}</p>
      {source.content_snippet && (
        <p className="sc-snippet">{source.content_snippet.slice(0, 200)}…</p>
      )}
      <a className="sc-url mono" href={source.url} target="_blank" rel="noreferrer">
        {source.url.slice(0, 60)}{source.url.length > 60 ? '…' : ''}
      </a>
    </div>
  )
}

export default function ClaimDetail({ claim, onClose, isPrintMode = false }) {
  const [showReflection, setShowReflection] = useState(false)
  const [showAllSources, setShowAllSources] = useState(false)

  const vm = getVerdict(claim.verdict)
  const typeColor = claimTypeColor(claim.claim_type)
  const confColor = confidenceColor(claim.confidence)

  const citedSource = (claim.all_sources || []).find(s => s.url === claim.source_url)
  const otherSources = (claim.all_sources || []).filter(s => s.url !== claim.source_url)

  return (
    <div className="claim-detail animate-in">
      {/* Header */}
      <div className="cd-header">
        <div className="cd-header-top">
          <span className="cd-type-badge mono" style={{ color: typeColor, borderColor: `${typeColor}33` }}>
            {claim.claim_type}
          </span>
          {claim.precision && claim.precision !== "N/A" && (
            <span className="cd-precision-badge mono" title="Mutation Analysis: Evidence Precision" style={{ 
              color: claim.precision === 'EXACT' ? 'var(--true)' : claim.precision === 'MISLEADING' ? 'var(--false)' : 'var(--partial)',
              border: `1px solid currentColor`, padding: '2px 6px', borderRadius: '4px', fontSize: '11px', marginLeft: '8px'
            }}>
              {claim.precision} MATCH
            </span>
          )}
          <span className="cd-id mono">claim #{claim.claim_id}</span>
          <button className="cd-close no-print" onClick={onClose}>✕</button>
        </div>
        <p className="cd-claim-text">{claim.claim_text}</p>
      </div>

      {/* Verdict hero */}
      <div className="cd-verdict-hero" style={{ background: vm.bg, borderColor: vm.border }}>
        <div className="cdv-left">
          <span className="cdv-symbol" style={{ color: vm.color }}>{vm.symbol}</span>
          <div>
            <div className="cdv-label mono" style={{ color: vm.color }}>{vm.label}</div>
            <div className="cdv-jury">
              {claim.jury_agreed
                ? <span className="jury-agreed">✓ Both models agreed</span>
                : <span className="jury-split">⚡ Models disagreed — second pass ran</span>
              }
            </div>
          </div>
        </div>
        <div className="cdv-right">
          <div className="cdv-conf-num mono" style={{ color: confColor }}>{claim.confidence}</div>
          <div className="cdv-conf-label">confidence</div>
          <div className="cdv-conf-bar">
            <div className="cdv-conf-fill" style={{ width: `${claim.confidence}%`, background: confColor }} />
          </div>
        </div>
      </div>

      {/* Temporal / Conflict warnings */}
      {claim.temporal_drift_flag && (
        <div className="cd-temporal-warning" style={{ background: 'rgba(245,166,35,0.1)', border: '1px solid rgba(245,166,35,0.3)', padding: '12px', borderRadius: '8px', marginBottom: '16px', color: 'var(--partial)', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span className="cw-icon">⏳</span>
          <span><strong>Potentially outdated source:</strong> Evidence for this temporal claim may not reflect the current state.</span>
        </div>
      )}

      {claim.conflict_flag && (
        <div className="cd-conflict-warning" style={{ background: 'rgba(247,97,79,0.1)', border: '1px solid rgba(247,97,79,0.3)', padding: '12px', borderRadius: '8px', marginBottom: '16px', color: 'var(--false)', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span className="cw-icon">⚡</span>
          <span><strong>Conflicting sources detected</strong> for this claim — see the Conflicts tab for details</span>
        </div>
      )}

      {/* Cited evidence */}
      {claim.cited_passage && claim.cited_passage !== 'No supporting passage found' && (
        <div className="cd-section">
          <div className="cd-section-title">Cited evidence</div>
          <blockquote className="cd-citation">
            <span className="cite-mark">"</span>
            {claim.cited_passage}
            <span className="cite-mark">"</span>
          </blockquote>
          {citedSource && (
            <div className="cd-cite-source mono">
              — {citedSource.domain}
              {citedSource.publish_date && ` · ${citedSource.publish_date.slice(0, 10)}`}
            </div>
          )}
        </div>
      )}

      {/* Reasoning */}
      {claim.reasoning && (
        <div className="cd-section">
          <div className="cd-section-title">Reasoning</div>
          <p className="cd-reasoning">{claim.reasoning}</p>
        </div>
      )}

      {/* Model verdicts (when split) */}
      {!claim.jury_agreed && (
        <div className="cd-section">
          <div className="cd-section-title">Model verdicts</div>
          <div className="cd-model-verdicts">
            {[
              { name: 'Llama 3.3 70B', verdict: claim.model_1_verdict, conf: claim.model_1_confidence },
              { name: 'Llama 3.1 8B', verdict: claim.model_2_verdict, conf: claim.model_2_confidence },
            ].map(m => {
              const mv = getVerdict(m.verdict)
              return (
                <div key={m.name} className="cd-model-row">
                  <span className="cd-model-name mono">{m.name}</span>
                  <span className="cd-model-verdict mono" style={{ color: mv.color, background: mv.bg, border: `1px solid ${mv.border}` }}>
                    {mv.label}
                  </span>
                  <span className="cd-model-conf mono" style={{ color: confidenceColor(m.conf) }}>{m.conf}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Self-reflection */}
      {claim.self_reflection_critique && (
        <div className="cd-section">
          <button className="cd-collapse-btn" onClick={() => setShowReflection(v => !v)}>
            <span>Self-reflection critique</span>
            <span className={`cd-strength ${claim.critique_strength > 60 ? 'high' : 'low'}`}>
              strength: {claim.critique_strength}
            </span>
            <span className="cd-chevron">{showReflection ? '▲' : '▼'}</span>
          </button>
          {(showReflection || isPrintMode) && (
            <div className="cd-reflection animate-fast">
              <p>{claim.self_reflection_critique}</p>
              {claim.critique_strength > 60 && (
                <div className="cd-recheck-note">↻ Re-search was triggered based on this critique</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Structured facts */}
      {claim.structured_facts?.length > 0 && (
        <div className="cd-section">
          <div className="cd-section-title">Structured knowledge</div>
          {claim.structured_facts.map((f, i) => (
            <div key={i} className="cd-structured-fact">
              <span className="sf-badge mono">{f.source}</span>
              <span className="sf-content">{f.content}</span>
            </div>
          ))}
        </div>
      )}

      {/* Sources */}
      {claim.all_sources?.length > 0 && (
        <div className="cd-section">
          <div className="cd-section-title">
            Sources ({claim.all_sources.length})
            <span className="cd-tier-legend">
              <span style={{ color: 'var(--true)' }}>T1</span>=authoritative
              <span style={{ color: 'var(--accent)' }}>T2</span>=established press
            </span>
          </div>
          {citedSource && <SourceCard source={citedSource} isCited={true} />}
          {!showAllSources && !isPrintMode && otherSources.length > 0 && (
            <button className="cd-show-more no-print" onClick={() => setShowAllSources(true)}>
              Show {otherSources.length} more source{otherSources.length > 1 ? 's' : ''}
            </button>
          )}
          {(showAllSources || isPrintMode) && otherSources.map((s, i) => (
            <SourceCard key={i} source={s} isCited={false} />
          ))}
        </div>
      )}
    </div>
  )
}
