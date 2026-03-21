import React from 'react'
import './ConflictPanel.css'

function AuthorityBar({ score }) {
  const color = score >= 1.0 ? 'var(--true)' : score >= 0.7 ? 'var(--accent)' : 'var(--text-muted)'
  const tier  = score >= 1.0 ? 'Tier 1' : score >= 0.7 ? 'Tier 2' : 'Tier 3'
  return (
    <span className="auth-bar">
      <span className="auth-tier mono" style={{ color }}>{tier}</span>
      <span className="auth-track">
        <span className="auth-fill" style={{ width: `${score * 100}%`, background: color }} />
      </span>
    </span>
  )
}

export default function ConflictPanel({ conflicts }) {
  if (!conflicts?.length) {
    return (
      <div className="conflict-empty">
        <span className="ce-icon">✓</span>
        <p>No conflicting sources detected across claims</p>
      </div>
    )
  }

  return (
    <div className="conflict-panel">
      <div className="cp-summary">
        <span className="cps-icon">⚡</span>
        <span className="cps-text">
          <strong>{conflicts.length}</strong> conflict{conflicts.length > 1 ? 's' : ''} detected — sources with opposing claims
        </span>
      </div>

      {conflicts.map((c, i) => (
        <div key={i} className="conflict-card animate-in" style={{ animationDelay: `${i * 0.05}s`, opacity: 0 }}>
          {/* Claim */}
          <div className="cc-claim">
            <span className="cc-claim-label mono">claim #{c.claim_id}</span>
            <p className="cc-claim-text">{c.claim_text}</p>
          </div>

          {/* Side-by-side */}
          <div className="cc-sides">
            {/* Source A */}
            <div className={`cc-side side-a ${c.better_supported === 'A' ? 'winning' : ''}`}>
              <div className="cc-side-header">
                <span className="cc-side-label mono">source a</span>
                {c.better_supported === 'A' && (
                  <span className="cc-better mono">better supported</span>
                )}
                <AuthorityBar score={c.source_a?.authority_score || 0.4} />
              </div>
              <div className="cc-domain mono">{c.source_a?.domain}</div>
              {c.source_a?.publish_date && (
                <div className="cc-date">{c.source_a.publish_date.slice(0, 10)}</div>
              )}
              <p className="cc-snippet">{c.source_a_summary}</p>
              {c.source_a?.url && (
                <a className="cc-url mono" href={c.source_a.url} target="_blank" rel="noreferrer">
                  {c.source_a.url.slice(0, 50)}…
                </a>
              )}
            </div>

            <div className="cc-vs">
              <span>vs</span>
            </div>

            {/* Source B */}
            <div className={`cc-side side-b ${c.better_supported === 'B' ? 'winning' : ''}`}>
              <div className="cc-side-header">
                <span className="cc-side-label mono">source b</span>
                {c.better_supported === 'B' && (
                  <span className="cc-better mono">better supported</span>
                )}
                <AuthorityBar score={c.source_b?.authority_score || 0.4} />
              </div>
              <div className="cc-domain mono">{c.source_b?.domain}</div>
              {c.source_b?.publish_date && (
                <div className="cc-date">{c.source_b.publish_date.slice(0, 10)}</div>
              )}
              <p className="cc-snippet">{c.source_b_summary}</p>
              {c.source_b?.url && (
                <a className="cc-url mono" href={c.source_b.url} target="_blank" rel="noreferrer">
                  {c.source_b.url.slice(0, 50)}…
                </a>
              )}
            </div>
          </div>

          {c.better_supported === 'equal' && (
            <div className="cc-equal-note mono">Both sources equally supported — verdict remains contested</div>
          )}
        </div>
      ))}
    </div>
  )
}
