import React, { useState } from 'react'
import { getVerdict, claimTypeColor } from '../utils'
import './LiveClaimCard.css'

export default function LiveClaimCard({ claim, update, queries }) {
  const [expanded, setExpanded] = useState(false)
  const status = update?.status || 'waiting'  // waiting | verifying | done
  const verdict = update?.verdict
  const confidence = update?.confidence
  const vm = verdict ? getVerdict(verdict) : null
  const typeColor = claimTypeColor(claim.claim_type)

  return (
    <div className={`live-card ${status} ${verdict ? `v-${verdict.replace(/\s+/g, '-')}` : ''}`}>
      <div className="live-card-main" onClick={() => status === 'done' && setExpanded(e => !e)}>
        {/* Left: status indicator */}
        <div className="lc-status-col">
          {status === 'waiting' && <div className="lc-dot waiting" />}
          {status === 'verifying' && <div className="lc-dot verifying"><span className="lc-spin" /></div>}
          {status === 'done' && vm && (
            <div className="lc-verdict-dot" style={{ background: vm.bg, border: `1.5px solid ${vm.border}` }}>
              <span style={{ color: vm.color, fontSize: '0.75rem' }}>{vm.symbol}</span>
            </div>
          )}
        </div>

        {/* Middle: claim text */}
        <div className="lc-content">
          <div className="lc-type-row">
            <span className="lc-type-badge mono" style={{ color: typeColor, borderColor: `${typeColor}33` }}>
              {claim.claim_type}
            </span>
            <span className="lc-id mono">#{claim.claim_id}</span>
          </div>
          <p className="lc-text">{claim.claim_text}</p>

          {/* Search queries feed */}
          {queries && status !== 'waiting' && (
            <div className="lc-queries">
              {queries.map((q, i) => (
                <span key={i} className={`lc-query ${i === 1 ? 'adversarial' : i === 2 ? 'contextual' : ''}`}>
                  <span className="query-tag mono">{i === 0 ? 'direct' : i === 1 ? 'adversarial' : 'contextual'}</span>
                  {q.length > 60 ? q.slice(0, 60) + '…' : q}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Right: verdict badge + confidence */}
        {status === 'done' && vm && (
          <div className="lc-verdict-col">
            <span className="lc-verdict-badge mono" style={{ color: vm.color, background: vm.bg, border: `1px solid ${vm.border}` }}>
              {vm.label}
            </span>
            <div className="lc-conf-bar">
              <div className="lc-conf-fill" style={{ width: `${confidence}%`, background: vm.color }} />
            </div>
            <span className="lc-conf-num mono" style={{ color: vm.color }}>{confidence}</span>
          </div>
        )}

        {status === 'verifying' && (
          <div className="lc-verifying-label mono">verifying...</div>
        )}

        {status === 'waiting' && (
          <div className="lc-waiting-label mono">queued</div>
        )}
      </div>

      {/* Conflict badge */}
      {update?.conflict_flag && (
        <div className="lc-conflict-flag">
          <span>⚡ Conflicting sources detected</span>
        </div>
      )}
    </div>
  )
}
