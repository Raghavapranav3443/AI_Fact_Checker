import React from 'react'
import './AIDetectionPanel.css'

function SignalBar({ label, value, description }) {
  const pct   = Math.round(value * 100)
  const color = pct > 65 ? 'var(--false)' : pct > 35 ? 'var(--partial)' : 'var(--true)'
  return (
    <div className="signal-row">
      <div className="signal-meta">
        <span className="signal-label">{label}</span>
        <span className="signal-desc">{description}</span>
      </div>
      <div className="signal-right">
        <div className="signal-track">
          <div className="signal-fill" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span className="signal-pct mono" style={{ color }}>{pct}%</span>
      </div>
    </div>
  )
}

export default function AIDetectionPanel({ data }) {
  if (!data) return null

  const { score, label, perplexity_signal, burstiness_signal, ngram_signal } = data
  const scoreColor = score > 65 ? 'var(--false)' : score > 35 ? 'var(--partial)' : 'var(--true)'

  const labelIcon = score > 65 ? '⚠' : score > 35 ? '◑' : '✓'

  return (
    <div className="ai-detection-panel">
      {/* Hero */}
      <div className="aidp-hero" style={{ borderColor: scoreColor + '33' }}>
        <div className="aidp-score-col">
          <div className="aidp-gauge">
            <svg viewBox="0 0 80 80" width="80" height="80">
              <circle cx="40" cy="40" r="32" fill="none" stroke="var(--bg-elevated)" strokeWidth="6" />
              <circle cx="40" cy="40" r="32" fill="none" stroke={scoreColor} strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={`${(score / 100) * 201} 201`}
                transform="rotate(-90 40 40)"
                style={{ transition: 'stroke-dasharray 0.8s ease' }}
              />
              <text x="40" y="38" textAnchor="middle" dominantBaseline="middle"
                style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, fill: scoreColor }}>
                {score}
              </text>
              <text x="40" y="53" textAnchor="middle"
                style={{ fontFamily: 'var(--font-mono)', fontSize: '6px', fill: 'var(--text-muted)' }}>
                / 100
              </text>
            </svg>
          </div>
          <div className="aidp-label-row">
            <span className="aidp-icon">{labelIcon}</span>
            <span className="aidp-label mono" style={{ color: scoreColor }}>{label}</span>
          </div>
        </div>

        <div className="aidp-explain">
          <p className="aidp-title">AI origin probability</p>
          <p className="aidp-desc">
            {score > 65
              ? 'This text exhibits strong hallmarks of AI generation: low perplexity, uniform sentence structure, and repetitive phrasing patterns.'
              : score > 35
              ? 'This text shows mixed signals — some characteristics consistent with AI generation alongside more varied human-like patterns.'
              : 'This text exhibits typical human writing characteristics: varied sentence structure, unpredictable phrasing, and natural burstiness.'}
          </p>
        </div>
      </div>

      {/* Signal breakdown */}
      <div className="aidp-signals">
        <div className="aidp-signals-title">Signal breakdown</div>
        <SignalBar
          label="Predictability"
          value={perplexity_signal}
          description="Low variance in word choice vs. AI baseline"
        />
        <SignalBar
          label="Uniformity"
          value={burstiness_signal}
          description="Coefficient of variation in sentence length (inverse)"
        />
        <SignalBar
          label="Repetition"
          value={ngram_signal}
          description="4-gram reuse ratio — AI text repeats phrases more"
        />
      </div>

      <div className="aidp-footer">
        Combined signal score (50% predictability + 30% uniformity + 20% repetition)
      </div>
    </div>
  )
}
