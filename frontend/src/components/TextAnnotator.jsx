import React, { useMemo } from 'react'
import { getVerdict } from '../utils'
import './TextAnnotator.css'

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export default function TextAnnotator({ text, claims, selectedClaimId, onSelectClaim }) {
  // Build a map of sentence → claim(s)
  const annotated = useMemo(() => {
    if (!text || !claims?.length) return [{ type: 'text', content: text }]

    // Sort claims by where their source_sentence appears in text (earliest first)
    const claimsWithPos = claims
      .filter(c => c.source_sentence && c.source_sentence.length > 10)
      .map(c => {
        const pos = text.indexOf(c.source_sentence.slice(0, 60))
        return { ...c, pos }
      })
      .filter(c => c.pos >= 0)
      .sort((a, b) => a.pos - b.pos)

    if (!claimsWithPos.length) return [{ type: 'text', content: text }]

    const segments = []
    let cursor = 0

    for (const claim of claimsWithPos) {
      // Find the sentence in the text
      const snippet = claim.source_sentence.slice(0, 80)
      const idx = text.indexOf(snippet, cursor)
      if (idx === -1) continue

      // Find the end of the full sentence (up to 300 chars or next period)
      let sentEnd = idx + claim.source_sentence.length
      if (sentEnd > text.length) sentEnd = text.length

      // Add text before this highlight
      if (idx > cursor) {
        segments.push({ type: 'text', content: text.slice(cursor, idx) })
      }

      // Add highlighted segment
      segments.push({
        type: 'highlight',
        content: text.slice(idx, sentEnd),
        claim,
      })

      cursor = sentEnd
    }

    // Remaining text
    if (cursor < text.length) {
      segments.push({ type: 'text', content: text.slice(cursor) })
    }

    return segments
  }, [text, claims])

  return (
    <div className="text-annotator">
      <div className="ta-legend">
        {[
          ['TRUE',           'var(--true)'],
          ['FALSE',          'var(--false)'],
          ['PARTIALLY TRUE', 'var(--partial)'],
          ['UNVERIFIABLE',   'var(--unverifiable)'],
          ['CONTESTED',      'var(--contested)'],
        ].map(([v, c]) => (
          <span key={v} className="ta-legend-item">
            <span className="ta-swatch" style={{ background: c }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
              {v === 'PARTIALLY TRUE' ? 'Partial' : v.charAt(0) + v.slice(1).toLowerCase()}
            </span>
          </span>
        ))}
        <span className="ta-hint">Click a highlight to inspect</span>
      </div>

      <div className="ta-text">
        {annotated.map((seg, i) => {
          if (seg.type === 'text') {
            return <span key={i}>{seg.content}</span>
          }

          const claim = seg.claim
          const update = claim.verdict
          const vm = update ? getVerdict(update) : null
          const isSelected = selectedClaimId === claim.claim_id

          return (
            <mark
              key={i}
              className={`ta-mark ${isSelected ? 'selected' : ''}`}
              style={{
                '--mark-color':  vm?.color  || 'var(--text-muted)',
                '--mark-bg':     vm?.bg     || 'rgba(136,153,187,0.1)',
                '--mark-border': vm?.border || 'rgba(136,153,187,0.2)',
              }}
              onClick={() => onSelectClaim(claim.claim_id)}
              title={`Claim #${claim.claim_id}: ${claim.verdict || 'pending'}`}
            >
              {seg.content}
              <sup className="ta-sup mono">#{claim.claim_id}</sup>
            </mark>
          )
        })}
      </div>
    </div>
  )
}
