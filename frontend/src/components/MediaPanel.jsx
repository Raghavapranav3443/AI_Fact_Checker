import React, { useState } from 'react'
import './MediaPanel.css'

function ImageCard({ result }) {
  const score = Math.round((result.ai_generated_score || 0) * 100)
  const isAI  = score > 65 || result.is_deepfake
  const color = score > 65 ? 'var(--false)' : score > 35 ? 'var(--partial)' : 'var(--true)'
  const [imgError, setImgError] = useState(false)

  return (
    <div className={`img-card ${isAI ? 'flagged' : ''}`}>
      {/* Thumbnail */}
      <div className="img-thumb">
        {imgError ? (
          <div className="img-fallback">
            <span>⊘</span>
            <span className="mono">no preview</span>
          </div>
        ) : (
          <img
            src={result.url}
            alt="analyzed"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        )}
        {/* Overlay badge */}
        <div className="img-overlay" style={{ borderColor: color }}>
          <span className="io-score mono" style={{ color }}>{score}%</span>
        </div>
      </div>

      {/* Info */}
      <div className="img-info">
        <div className="img-badges">
          <span className="img-badge mono" style={{ color, background: color + '18', borderColor: color + '44' }}>
            {score > 65 ? 'AI Generated' : score > 35 ? 'Uncertain' : 'Likely Real'}
          </span>
          {result.is_deepfake && (
            <span className="img-badge deepfake mono">Deepfake</span>
          )}
        </div>
        {result.error ? (
          <p className="img-error">Analysis failed: {result.error}</p>
        ) : (
          <p className="img-url">{result.url.split('/').pop()?.slice(0, 30) || 'image'}</p>
        )}
      </div>
    </div>
  )
}

export default function MediaPanel({ results }) {
  if (!results?.length) {
    return (
      <div className="media-empty">
        <span className="me-icon">⊘</span>
        <p>No images were found or analysed</p>
        <p className="me-hint">Media detection only runs when input is a URL</p>
      </div>
    )
  }

  const flagged = results.filter(r => (r.ai_generated_score || 0) > 0.65 || r.is_deepfake)
  const clean   = results.filter(r => (r.ai_generated_score || 0) <= 0.65 && !r.is_deepfake)

  return (
    <div className="media-panel">
      {/* Summary */}
      <div className={`mp-summary ${flagged.length > 0 ? 'has-flags' : 'all-clear'}`}>
        {flagged.length > 0 ? (
          <>
            <span className="mps-icon">⚠</span>
            <span>
              <strong>{flagged.length}</strong> image{flagged.length > 1 ? 's' : ''} flagged as likely AI-generated or manipulated
            </span>
          </>
        ) : (
          <>
            <span className="mps-icon">✓</span>
            <span>All {results.length} image{results.length > 1 ? 's' : ''} appear authentic</span>
          </>
        )}
      </div>

      {/* Grid */}
      <div className="mp-grid">
        {results.map((r, i) => (
          <ImageCard key={i} result={r} />
        ))}
      </div>
    </div>
  )
}
