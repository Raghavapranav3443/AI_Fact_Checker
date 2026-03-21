import React from 'react'
import { trustLabel, confidenceColor } from '../utils'
import './TrustScore.css'

const VERDICT_COLORS = {
  'TRUE':           'var(--true)',
  'FALSE':          'var(--false)',
  'PARTIALLY TRUE': 'var(--partial)',
  'UNVERIFIABLE':   'var(--unverifiable)',
  'CONTESTED':      'var(--contested)',
}

export default function TrustScore({ score, breakdown }) {
  const color = confidenceColor(score)
  const label = trustLabel(score)

  // SVG ring params
  const R = 44, CX = 56, CY = 56
  const circumference = 2 * Math.PI * R
  const filled = (score / 100) * circumference

  const total = Object.values(breakdown || {}).reduce((a, b) => a + b, 0)

  return (
    <div className="trust-score-card">
      {/* Ring gauge */}
      <div className="ts-gauge">
        <svg width="112" height="112" viewBox="0 0 112 112">
          {/* Track */}
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="var(--bg-elevated)" strokeWidth="7" />
          {/* Fill */}
          <circle
            cx={CX} cy={CY} r={R}
            fill="none"
            stroke={color}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            transform={`rotate(-90 ${CX} ${CY})`}
            style={{ transition: 'stroke-dasharray 0.8s ease, stroke 0.4s' }}
          />
          {/* Score text */}
          <text x={CX} y={CY - 6} textAnchor="middle" dominantBaseline="middle"
            style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 700, fill: color }}>
            {score}
          </text>
          <text x={CX} y={CY + 14} textAnchor="middle"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', fill: 'var(--text-muted)', letterSpacing: '0.5px' }}>
            / 100
          </text>
        </svg>
        <div className="ts-label" style={{ color }}>{label}</div>
      </div>

      {/* Breakdown bars */}
      <div className="ts-breakdown">
        {Object.entries(breakdown || {}).filter(([, n]) => n > 0).map(([verdict, count]) => {
          const pct = total > 0 ? (count / total) * 100 : 0
          const color = VERDICT_COLORS[verdict] || 'var(--text-muted)'
          const label = verdict === 'PARTIALLY TRUE' ? 'Partial' : verdict.charAt(0) + verdict.slice(1).toLowerCase()
          return (
            <div key={verdict} className="ts-bar-row">
              <span className="ts-bar-label" style={{ color }}>{label}</span>
              <div className="ts-bar-track">
                <div className="ts-bar-fill" style={{ width: `${pct}%`, background: color }} />
              </div>
              <span className="ts-bar-count mono" style={{ color }}>{count}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
