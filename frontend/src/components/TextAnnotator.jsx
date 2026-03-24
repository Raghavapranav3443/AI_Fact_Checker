import React, { useMemo } from 'react'
import { getVerdict } from '../utils'
import './TextAnnotator.css'

// ── Normalise whitespace for matching ────────────────────────────────────────
// Scraped/LLM text often has \n or multiple spaces where the other side has one.
function normalise(str) {
  return str.replace(/\s+/g, ' ').trim()
}

// ── Find best match position in normalised text ───────────────────────────────
// Returns { start, end } as positions in normText, or null.
// 'end' is always the position of the LAST MATCHED CHARACTER + 1,
// never overshooting normText.length.
function findMatch(normText, normSentence) {
  if (!normSentence || normSentence.length < 10) return null

  // Pass 1: try full sentence first, then 80-char prefix as overshoot fallback
  const full = normSentence
  let idx = normText.indexOf(full)
  if (idx !== -1) {
    return { start: idx, end: idx + full.length }
  }
  // Full sentence not found — try first 80 chars (handles LLM adding extra at end)
  if (full.length > 80) {
    const s80 = full.slice(0, 80)
    idx = normText.indexOf(s80)
    if (idx !== -1) {
      return { start: idx, end: idx + s80.length }
    }
  }

  // Pass 2: 40-char prefix (handles heavier LLM paraphrasing at the end)
  if (full.length > 40) {
    const s40 = full.slice(0, 40)
    idx = normText.indexOf(s40)
    if (idx !== -1) {
      return { start: idx, end: idx + s40.length }
    }
  }

  // Pass 3: binary search for longest leading prefix (≥20 chars) in normText.
  // Handles cases where LLM lightly paraphrases the middle/end of the sentence.
  // end = best + bestLen (actual matched chars, not full sentence length).
  let lo = 20, hi = Math.min(full.length, 120), best = -1, bestLen = 0
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2)
    const probe = full.slice(0, mid)
    const found = normText.indexOf(probe)
    if (found !== -1) { best = found; bestLen = mid; lo = mid + 1 }
    else { hi = mid - 1 }
  }
  if (best !== -1 && bestLen >= 20) {
    return { start: best, end: best + bestLen }
  }

  return null
}

// ── Map normalised text positions back to original text positions ─────────────
// normalise() collapses whitespace runs to a single space.
// This map lets us convert a position in the normalised string
// back to the corresponding position in the original string.
// map[normIndex] = origIndex
function buildPosMap(origText) {
  const map = []
  let ni = 0
  let inSpace = false
  for (let oi = 0; oi < origText.length; oi++) {
    const ch = origText[oi]
    if (/\s/.test(ch)) {
      if (!inSpace) { map[ni] = oi; ni++; inSpace = true }
      // consecutive whitespace in orig: skip (they collapse to one space in norm)
    } else {
      map[ni] = oi; ni++; inSpace = false
    }
  }
  map[ni] = origText.length // sentinel: normText.length → origText.length
  return map
}

export default function TextAnnotator({ text, claims, selectedClaimId, onSelectClaim }) {
    const annotated = useMemo(() => {
      if (!text || !claims?.length) return [{ type: 'text', content: text || '' }]

      // Group claims by their character offsets to handle multi-claim sentences
      const groups = []
      claims.forEach(c => {
        // Only process claims with valid offsets from backend
        if (typeof c.start_char !== 'number' || typeof c.end_char !== 'number') return
        if (c.start_char === 0 && c.end_char === 0) return // Fallback failed

        let group = groups.find(g => g.start === c.start_char && g.end === c.end_char)
        if (group) {
          group.claims.push(c)
        } else {
          groups.push({ start: c.start_char, end: c.end_char, claims: [c] })
        }
      })

      // Sort groups by appearance
      groups.sort((a, b) => a.start - b.start)

      if (!groups.length) return [{ type: 'text', content: text }]

      const segments = []
      let cursor = 0

      for (const group of groups) {
        // Skip overlapping segments (shouldn't happen with sentence-based extraction, but for safety)
        if (group.start < cursor) continue

        if (group.start > cursor) {
          segments.push({ type: 'text', content: text.slice(cursor, group.start) })
        }

        const end = Math.min(group.end, text.length)
        segments.push({
          type: 'highlight',
          content: text.slice(group.start, end),
          claims: group.claims
        })
        cursor = end
      }

      if (cursor < text.length) {
        segments.push({ type: 'text', content: text.slice(cursor) })
      }

      return segments
    }, [text, claims])

    // Use stable ID from backend for numbering to keep consistency with sidebar
    const displayNumMap = useMemo(() => {
      const map = {}
      claims?.forEach(c => {
        map[c.claim_id] = c.claim_id
      })
      return map
    }, [claims])

    const highlightedCount = useMemo(() => {
      const ids = new Set()
      annotated.forEach(seg => {
        if (seg.type === 'highlight') {
          seg.claims.forEach(c => ids.add(c.claim_id))
        }
      })
      return ids.size
    }, [annotated])

    const totalCount = claims?.length || 0
    const missedCount = totalCount - highlightedCount

  return (
    <div className="text-annotator">
      <div className="ta-legend">
        {[
          ['TRUE', 'var(--true)'],
          ['FALSE', 'var(--false)'],
          ['PARTIALLY TRUE', 'var(--partial)'],
          ['UNVERIFIABLE', 'var(--unverifiable)'],
          ['CONTESTED', 'var(--contested)'],
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

      {missedCount > 0 && (
        <div className="ta-coverage-note mono">
          {highlightedCount}/{totalCount} claims highlighted
          {missedCount === 1
            ? ' · 1 claim could not be located in source text'
            : ` · ${missedCount} claims could not be located in source text`}
        </div>
      )}

      <div className="ta-text">
        {annotated.map((seg, i) => {
          if (seg.type === 'text') {
            return <span key={i}>{seg.content}</span>
          }

          const { claims: groupClaims } = seg
          // Pick a representative verdict for coloring (priority: FALSE > CONTESTED > PARTIAL > UNVERIFIABLE > TRUE)
          const verdictPriority = { 'FALSE': 5, 'CONTESTED': 4, 'PARTIALLY TRUE': 3, 'UNVERIFIABLE': 2, 'TRUE': 1, null: 0 }
          const representativeClaim = [...groupClaims].sort((a, b) => 
            (verdictPriority[b.verdict] || 0) - (verdictPriority[a.verdict] || 0)
          )[0]
          
          const vm = representativeClaim.verdict ? getVerdict(representativeClaim.verdict) : null
          const isSelected = groupClaims.some(c => c.claim_id === selectedClaimId)
          const titleText = groupClaims.map(c => `Claim #${c.claim_id}: ${c.verdict || 'pending'}`).join('\n')

          return (
            <mark
              key={i}
              className={`ta-mark ${isSelected ? 'selected' : ''}`}
              style={{
                '--mark-color': vm?.color || 'var(--text-muted)',
                '--mark-bg': vm?.bg || 'rgba(136,153,187,0.1)',
                '--mark-border': vm?.border || 'rgba(136,153,187,0.2)',
              }}
              onClick={() => onSelectClaim(groupClaims[0].claim_id)}
              title={titleText}
            >
              {seg.content}
              {groupClaims.map((c, idx) => (
                <sup key={c.claim_id} className="ta-sup mono">
                  {idx > 0 && ','}#{displayNumMap[c.claim_id]}
                </sup>
              ))}
            </mark>
          )
        })}
      </div>
    </div>
  )
}