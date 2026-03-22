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

    const normText = normalise(text)
    const posMap = buildPosMap(text)

    const matched = claims
      .filter(c => {
        // source_sentence takes priority; fall back to claim_text.
        // Guard against whitespace-only strings which normalise to '' and can't match.
        const s = normalise(c.source_sentence || c.claim_text || '')
        return s.length >= 10
      })
      .map(c => {
        const normSentence = normalise(c.source_sentence || c.claim_text)
        const match = findMatch(normText, normSentence)
        if (!match) return null
        // Convert norm positions → orig positions via posMap
        const origStart = posMap[match.start] ?? match.start
        const origEnd = posMap[Math.min(match.end, posMap.length - 1)] ?? match.end
        return { claim: c, origStart, origEnd }
      })
      .filter(Boolean)
      .sort((a, b) => a.origStart - b.origStart)

    if (!matched.length) return [{ type: 'text', content: text }]

    const segments = []
    let cursor = 0

    for (const { claim, origStart, origEnd } of matched) {
      // Skip overlapping matches — first claim in text order wins
      if (origStart < cursor) continue

      if (origStart > cursor) {
        segments.push({ type: 'text', content: text.slice(cursor, origStart) })
      }

      const end = Math.min(origEnd, text.length)
      segments.push({ type: 'highlight', content: text.slice(origStart, end), claim })
      cursor = end
    }

    if (cursor < text.length) {
      segments.push({ type: 'text', content: text.slice(cursor) })
    }

    return segments
  }, [text, claims])

  // Sequential display numbers based solely on highlighted claims in text order.
  // Avoids gaps like #1 → #4 when some claims fail to match.
  const displayNumMap = useMemo(() => {
    const map = {}
    let n = 1
    for (const seg of annotated) {
      if (seg.type === 'highlight') map[seg.claim.claim_id] = n++
    }
    return map
  }, [annotated])

  const highlightedCount = Object.keys(displayNumMap).length
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

          const { claim } = seg
          const vm = claim.verdict ? getVerdict(claim.verdict) : null
          const isSelected = selectedClaimId === claim.claim_id
          const displayNum = displayNumMap[claim.claim_id] ?? claim.claim_id

          return (
            <mark
              key={i}
              className={`ta-mark ${isSelected ? 'selected' : ''}`}
              style={{
                '--mark-color': vm?.color || 'var(--text-muted)',
                '--mark-bg': vm?.bg || 'rgba(136,153,187,0.1)',
                '--mark-border': vm?.border || 'rgba(136,153,187,0.2)',
              }}
              onClick={() => onSelectClaim(claim.claim_id)}
              title={`Claim #${displayNum}: ${claim.verdict || 'pending'}`}
            >
              {seg.content}
              <sup className="ta-sup mono">#{displayNum}</sup>
            </mark>
          )
        })}
      </div>
    </div>
  )
}