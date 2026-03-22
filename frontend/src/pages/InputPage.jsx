import React, { useState, useRef } from 'react'
import axios from 'axios'
import { usePipelineContext } from '../context/PipelineContext'
import './InputPage.css'

const MIN_WORDS = 5
const MAX_WORDS = 10000

function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function isValidUrl(str) {
  try { new URL(str); return true } catch { return false }
}

export default function InputPage() {
  const { setSessionId, setInputText, setInputMeta, setPage } = usePipelineContext()
  const [mode, setMode]       = useState('text') // 'text' | 'url'
  const [text, setText]       = useState('')
  const [url, setUrl]         = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const textareaRef           = useRef(null)

  const words    = wordCount(text)
  const urlValid = isValidUrl(url)
  const textValid = words >= MIN_WORDS && words <= MAX_WORDS
  const canSubmit = mode === 'url' ? (urlValid && !loading) : (textValid && !loading)

  async function handleSubmit() {
    if (!canSubmit) return
    setLoading(true)
    setError('')
    try {
      const payload = mode === 'url'
        ? { type: 'url', content: url }
        : { type: 'text', content: text }

      const res = await axios.post('/api/ingest', payload)
      const { session_id, word_count, estimated_time_seconds } = res.data

      setSessionId(session_id)
      setInputText(mode === 'text' ? text : url)
      setInputMeta({ word_count, estimated_time_seconds })
      setPage('pipeline')
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start analysis. Check your input and try again.')
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
  }

  return (
    <div className="input-page">
      {/* Header */}
      <header className="input-header">
        <div className="logo-mark" onClick={() => setPage('landing')} style={{ cursor: 'pointer' }}>
          <span className="logo-v">V</span>
          <span className="logo-text">ERITAS</span>
        </div>
        <p className="logo-sub">Trust Intelligence Platform</p>
      </header>

      {/* Main card */}
      <main className="input-main">
        <div className="input-card animate-in">
          {/* Mode toggle */}
          <div className="mode-toggle">
            <button
              className={`mode-btn ${mode === 'text' ? 'active' : ''}`}
              onClick={() => { setMode('text'); setError('') }}
            >
              <span className="mode-icon">¶</span> Paste Text
            </button>
            <button
              className={`mode-btn ${mode === 'url' ? 'active' : ''}`}
              onClick={() => { setMode('url'); setError('') }}
            >
              <span className="mode-icon">⌁</span> Enter URL <span className="wip-badge mono" style={{ fontSize: '9px', verticalAlign: 'middle', marginLeft: '4px', opacity: 0.5 }}>(work in progress)</span>
            </button>
          </div>

          {/* Input area */}
          {mode === 'text' ? (
            <div className="textarea-wrap">
              <textarea
                ref={textareaRef}
                className="main-textarea"
                placeholder="Paste an article, essay, or any text to fact-check..."
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                spellCheck={false}
              />
              <div className="textarea-footer">
                <span className={`word-count ${words < MIN_WORDS ? 'warn' : words > MAX_WORDS ? 'danger' : 'ok'}`}>
                  <span className="mono">{words.toLocaleString()}</span> / {MAX_WORDS.toLocaleString()} words
                  {words < MIN_WORDS && words > 0 && <span className="count-hint"> — need {MIN_WORDS - words} more</span>}
                </span>
                <span className="shortcut-hint">⌘↵ to submit</span>
              </div>
            </div>
          ) : (
            <div className="url-wrap">
              <div className={`url-input-row ${urlValid ? 'valid' : ''}`}>
                <span className="url-prefix mono">https://</span>
                <input
                  className="url-input"
                  placeholder="paste article URL here..."
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                  spellCheck={false}
                />
                {urlValid && <span className="url-check">✓</span>}
              </div>
              <p className="url-hint">We'll scrape the article and extract images for deepfake detection.</p>
              <div className="url-logic-pointer mono" style={{ fontSize: '11px', marginTop: '12px', color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <p style={{ marginBottom: '8px', color: 'var(--accent)' }}>Feel free to check out the backend logic :)</p>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  <li>→ <code>backend/agents/media_detector.py</code> (Deepfake Analysis)</li>
                  <li>→ <code>backend/utils/scraper.py</code> (Image Extraction)</li>
                </ul>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="input-error animate-fast">
              <span className="error-icon">⚠</span> {error}
            </div>
          )}

          {/* Submit */}
          <button
            className={`submit-btn ${canSubmit ? 'ready' : ''} ${loading ? 'loading' : ''}`}
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {loading ? (
              <><span className="spinner" /> Scraping &amp; starting pipeline...</>
            ) : (
              <><span className="btn-icon">⟴</span> Analyse for truth</>
            )}
          </button>
        </div>

        {/* Feature pills */}
        <div className="feature-pills animate-in" style={{ animationDelay: '0.1s', opacity: 0 }}>
          {[
            ['⊛', 'Triple-query evidence retrieval'],
            ['⊚', 'Dual-tier Llama 3 Jury'],
            ['⊝', 'Conflict detection'],
            ['⊜', 'AI text & media detection'],
          ].map(([icon, label]) => (
            <span key={label} className="pill">
              <span className="pill-icon">{icon}</span>{label}
            </span>
          ))}
        </div>
      </main>
    </div>
  )
}
