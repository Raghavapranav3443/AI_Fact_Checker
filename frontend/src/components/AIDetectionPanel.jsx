import React from 'react'
import './AIDetectionPanel.css'

function SignalBar({ label, value, description }) {
  const pct = Math.round((value ?? 0.5) * 100)
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

  const { score, label } = data

  // Resolve with fallback — handles both new and legacy backend responses
  const burst = data.burstiness_signal ?? data.perplexity_signal ?? 0.5
  const unif = data.uniformity_signal ?? data.ngram_signal ?? 0.5
  const fw = data.function_words_signal ?? 0.5
  const punct = data.punctuation_signal ?? 0.5

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
              ? 'Strong AI-generation markers: uniform sentence lengths, low function-word density, consistent punctuation, and tight length clustering.'
              : score > 35
                ? 'Mixed signals — some characteristics consistent with AI generation, others more typical of human writing.'
                : 'Typical human writing: varied sentence structure, natural burstiness, high function-word density, and irregular punctuation.'}
          </p>
        </div>
      </div>

      {/* Signal breakdown */}
      <div className="aidp-signals">
        <div className="aidp-signals-title">Signal breakdown</div>
        <SignalBar
          label="Sentence Burstiness"
          value={burst}
          description="Low length variation (CV) — AI writes sentences of uniform length"
        />
        <SignalBar
          label="Length Clustering"
          value={unif}
          description="High fraction of sentences within ±4 words of mean — AI clusters tightly"
        />
        <SignalBar
          label="Function Word Density"
          value={fw}
          description="Low ratio of the/I/and/but — AI favours content words over connectives"
        />
        <SignalBar
          label="Punctuation Regularity"
          value={punct}
          description="Low punctuation variance per sentence — AI punctuates with machine consistency"
        />
      </div>

      <div className="aidp-footer">
        Deterministic signals — no LLM (30% burstiness · 25% clustering · 25% function words · 20% punctuation)
      </div>
    </div>
  )
}