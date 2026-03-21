import React from 'react'
import './StageIndicator.css'

const STAGES = [
  { key: 'extracting',  label: 'Extract',  desc: 'Claim decomposition' },
  { key: 'retrieving',  label: 'Search',   desc: 'Evidence retrieval' },
  { key: 'verifying',   label: 'Verify',   desc: 'Cross-model jury' },
  { key: 'analyzing',   label: 'Analyse',  desc: 'AI & media detection' },
]

const STAGE_ORDER = ['extracting', 'retrieving', 'verifying', 'analyzing', 'complete']

function getStatus(stageKey, currentStage) {
  const cur = STAGE_ORDER.indexOf(currentStage)
  const idx = STAGE_ORDER.indexOf(stageKey)
  if (idx < cur) return 'done'
  if (idx === cur) return 'active'
  return 'pending'
}

export default function StageIndicator({ currentStage }) {
  return (
    <div className="stage-indicator">
      {STAGES.map((s, i) => {
        const status = getStatus(s.key, currentStage)
        return (
          <React.Fragment key={s.key}>
            <div className={`stage-step ${status}`}>
              <div className="step-dot">
                {status === 'done' && <span className="step-check">✓</span>}
                {status === 'active' && <span className="step-pulse" />}
                {status === 'pending' && <span className="step-num mono">{i + 1}</span>}
              </div>
              <div className="step-labels">
                <span className="step-label">{s.label}</span>
                <span className="step-desc">{s.desc}</span>
              </div>
            </div>
            {i < STAGES.length - 1 && (
              <div className={`stage-connector ${status === 'done' ? 'filled' : ''}`} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
