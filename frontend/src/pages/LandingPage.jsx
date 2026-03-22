import React, { useEffect, useRef, useState } from 'react'
import { usePipelineContext } from '../context/PipelineContext'
import './LandingPage.css'

/* ── Animated trust score ring ── */
function TrustRing({ score, color, label }) {
  const R = 36, C = 44
  const circ = 2 * Math.PI * R
  const [filled, setFilled] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setFilled((score / 100) * circ), 300)
    return () => clearTimeout(t)
  }, [score, circ])
  return (
    <div className="demo-ring">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle cx={C} cy={C} r={R} fill="none" stroke="var(--bg-elevated)" strokeWidth="5" />
        <circle cx={C} cy={C} r={R} fill="none" stroke={color} strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ}`}
          transform={`rotate(-90 ${C} ${C})`}
          style={{ transition: 'stroke-dasharray 1.2s ease' }}
        />
        <text x={C} y={C - 4} textAnchor="middle" dominantBaseline="middle"
          style={{ fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 700, fill: color }}>
          {score}
        </text>
        <text x={C} y={C + 12} textAnchor="middle"
          style={{ fontFamily: 'var(--font-mono)', fontSize: '6px', fill: 'var(--text-muted)', letterSpacing: '0.5px' }}>
          / 100
        </text>
      </svg>
      <span className="demo-ring-label" style={{ color }}>{label}</span>
    </div>
  )
}

/* ── Scroll reveal hook ── */
function useReveal(threshold = 0.1) {
  const ref = useRef(null)
  const [vis, setVis] = useState(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVis(true); obs.disconnect() } },
      { threshold }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])
  return [ref, vis]
}

/* ── Animated counter ── */
function Counter({ to, suffix = '' }) {
  const [val, setVal] = useState(0)
  const ref = useRef(null)
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return
      obs.disconnect()
      let start = 0
      const step = to / 60
      const id = setInterval(() => {
        start = Math.min(start + step, to)
        setVal(Math.round(start))
        if (start >= to) clearInterval(id)
      }, 16)
    }, { threshold: 0.5 })
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [to])
  return <span ref={ref}>{val}{suffix}</span>
}

const PIPELINE_STEPS = [
  {
    num: '01',
    title: 'Input Classification',
    sub: 'Llama 3.1 8B fuse',
    desc: 'A lightweight model gates every submission — classifying input as Factual, Opinion, or Off-Topic before a single API call is made downstream.',
    color: 'var(--accent)',
    icon: '⊛',
  },
  {
    num: '02',
    title: 'Atomic Claim Extraction',
    sub: 'Llama 3.3 70B',
    desc: 'Complex text is decomposed into discrete, typed, verifiable statements — Temporal, Statistical, Entity-State, or Historical-Fact — with source sentence preserved.',
    color: 'var(--true)',
    icon: '⊚',
  },
  {
    num: '03',
    title: 'Triple-Query Retrieval',
    sub: 'Tavily + 4 Knowledge APIs',
    desc: 'Each claim generates three search queries: Direct, Adversarial, and Contextual. Evidence is cross-referenced from Tavily, Wikidata, Wikipedia, WorldBank, and OpenFDA in parallel.',
    color: 'var(--partial)',
    icon: '⊝',
  },
  {
    num: '04',
    title: 'Dual-Model Jury',
    sub: 'Llama 3.3 70B × Llama 3.1 8B',
    desc: 'Two independent models verify each claim against evidence exclusively — training knowledge is inadmissible. Disagreement triggers a CONTESTED verdict and re-search.',
    color: 'var(--contested)',
    icon: '⊞',
  },
  {
    num: '05',
    title: 'Self-Reflection & Conflicts',
    sub: 'Reflector + Conflict Detector',
    desc: 'A critic model challenges every verdict. If critique strength exceeds 60, re-search is triggered. Source contradictions are surfaced as a side-by-side conflict panel.',
    color: 'var(--false)',
    icon: '⊟',
  },
]

const VERDICT_EXAMPLES = [
  { verdict: 'TRUE', color: 'var(--true)', bg: 'var(--true-bg)', border: 'var(--true-border)', symbol: '✓', claim: 'The WHO was established on April 7, 1948.' },
  { verdict: 'FALSE', color: 'var(--false)', bg: 'var(--false-bg)', border: 'var(--false-border)', symbol: '✗', claim: 'AlphaGo won all five matches against Lee Sedol.' },
  { verdict: 'PARTIALLY TRUE', color: 'var(--partial)', bg: 'var(--partial-bg)', border: 'var(--partial-border)', symbol: '◑', claim: 'OpenAI was founded in 2015 as a non-profit.' },
  { verdict: 'CONTESTED', color: 'var(--contested)', bg: 'var(--contested-bg)', border: 'var(--contested-border)', symbol: '⚡', claim: "China's 2023 GDP growth was 5.2 percent." },
  { verdict: 'UNVERIFIABLE', color: 'var(--unverifiable)', bg: 'var(--unverifiable-bg)', border: 'var(--unverifiable-border)', symbol: '?', claim: 'The company employs approximately 8,000 people.' },
]

export default function LandingPage() {
  const { setPage } = usePipelineContext()
  const [heroRef, heroVis] = useReveal(0.01)
  const [pipeRef, pipeVis] = useReveal(0.05)
  const [demoRef, demoVis] = useReveal(0.05)
  const [statsRef, statsVis] = useReveal(0.2)

  return (
    <div className="lp">

      {/* ── NAV ── */}
      <nav className="lp-nav">
        <div className="lp-nav-logo">
          <span className="lp-nav-v">V</span><span className="lp-nav-rest">ERITAS</span>
        </div>
        <button className="lp-nav-cta" onClick={() => setPage('input')}>
          Start Analysing →
        </button>
      </nav>

      {/* ── HERO ── */}
      <section className="lp-hero" ref={heroRef}>
        <div className="lp-hero-bg">
          <div className="lp-orb lp-orb-1" />
          <div className="lp-orb lp-orb-2" />
          <div className="lp-grid-lines" aria-hidden="true" />
        </div>

        <div className={`lp-hero-content ${heroVis ? 'is-visible' : ''}`}>
          <div className="lp-hero-badge mono">
            <span className="lp-hero-badge-dot" /> AI-Powered Fact Verification
          </div>

          <h1 className="lp-hero-title display">
            Every claim.<br />
            <span className="lp-hero-title-accent">Verified.</span>
          </h1>

          <p className="lp-hero-sub">
            Veritas decomposes articles into atomic facts, retrieves real-world evidence
            from authoritative sources, and cross-validates with a dual-model jury —
            delivering a granular accuracy report with citations and confidence scores.
          </p>

          <div className="lp-hero-actions">
            <button className="lp-btn-primary" onClick={() => setPage('input')}>
              Analyse an article
            </button>
            <a href="#how-it-works" className="lp-btn-ghost">
              See how it works ↓
            </a>
          </div>

          {/* Live verdict preview */}
          <div className="lp-hero-preview">
            {VERDICT_EXAMPLES.map((v, i) => (
              <div
                key={v.verdict}
                className="lp-preview-chip"
                style={{
                  background: v.bg,
                  border: `1px solid ${v.border}`,
                  animationDelay: `${i * 0.1}s`,
                }}
              >
                <span className="lp-preview-symbol mono" style={{ color: v.color }}>{v.symbol}</span>
                <span className="lp-preview-text">{v.claim}</span>
                <span className="lp-preview-verdict mono" style={{ color: v.color }}>{v.verdict}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section className="lp-stats" ref={statsRef}>
        {[
          { num: 12, suffix: '', label: 'Claims per analysis' },
          { num: 3, suffix: 'x', label: 'Queries per claim' },
          { num: 2, suffix: '', label: 'Independent verifier models' },
          { num: 5, suffix: '', label: 'Intelligence stages' },
        ].map(({ num, suffix, label }) => (
          <div key={label} className="lp-stat">
            <div className="lp-stat-num display">
              {statsVis ? <Counter to={num} suffix={suffix} /> : `0${suffix}`}
            </div>
            <div className="lp-stat-label">{label}</div>
          </div>
        ))}
      </section>

      {/* ── PIPELINE ── */}
      <section className="lp-pipeline" id="how-it-works" ref={pipeRef}>
        <div className="lp-section-head">
          <span className="lp-eyebrow mono">The Pipeline</span>
          <h2 className="lp-section-title display">Five stages.<br />Zero hallucinations.</h2>
          <p className="lp-section-sub">
            Every submission passes through a strict sequential pipeline.
            No stage trusts the previous one blindly.
          </p>
        </div>

        <div className={`lp-steps ${pipeVis ? 'is-visible' : ''}`}>
          {PIPELINE_STEPS.map((step, i) => (
            <div
              key={step.num}
              className="lp-step"
              style={{ '--delay': `${i * 0.1}s` }}
            >
              <div className="lp-step-left">
                <div className="lp-step-icon" style={{ color: step.color, background: `${step.color}18`, border: `1px solid ${step.color}33` }}>
                  {step.icon}
                </div>
                {i < PIPELINE_STEPS.length - 1 && <div className="lp-step-line" />}
              </div>
              <div className="lp-step-body">
                <div className="lp-step-meta">
                  <span className="lp-step-num mono" style={{ color: step.color }}>{step.num}</span>
                  <span className="lp-step-sub mono">{step.sub}</span>
                </div>
                <h3 className="lp-step-title">{step.title}</h3>
                <p className="lp-step-desc">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── DEMO OUTCOMES ── */}
      <section className="lp-demo" ref={demoRef}>
        <div className="lp-section-head">
          <span className="lp-eyebrow mono">What you get</span>
          <h2 className="lp-section-title display">Three demo scenarios.<br />Three different truths.</h2>
        </div>

        <div className={`lp-demo-cards ${demoVis ? 'is-visible' : ''}`}>
          {[
            {
              label: 'Mostly True',
              title: 'Well-sourced article',
              desc: 'WHO founding facts. High authority sources, recent citations, both models agree.',
              score: 82,
              color: 'var(--true)',
              verdicts: [8, 1, 0, 1, 0],
              delay: '0s',
            },
            {
              label: 'Mixed Accuracy',
              title: 'AI industry blog',
              desc: 'Claims about OpenAI, Google DeepMind, and Nvidia — some accurate, some not.',
              score: 51,
              color: 'var(--partial)',
              verdicts: [3, 3, 2, 1, 1],
              delay: '0.1s',
            },
            {
              label: 'Conflicting Sources',
              title: 'Economic claims',
              desc: 'IMF vs World Bank figures. CONTESTED verdicts, conflict panel populated.',
              score: 34,
              color: 'var(--contested)',
              verdicts: [2, 1, 2, 3, 2],
              delay: '0.2s',
            },
          ].map(({ label, title, desc, score, color, verdicts, delay }) => (
            <div key={title} className="lp-demo-card" style={{ '--delay': delay }}>
              <div className="lp-demo-card-top">
                <TrustRing score={score} color={color} label={label} />
                <div className="lp-demo-card-info">
                  <div className="lp-demo-card-title">{title}</div>
                  <p className="lp-demo-card-desc">{desc}</p>
                </div>
              </div>
              <div className="lp-demo-verdict-bars">
                {['TRUE', 'FALSE', 'PARTIAL', 'CONTESTED', 'UNVERIFIABLE'].map((v, i) => (
                  <div key={v} className="lp-demo-bar-row">
                    <span className="lp-demo-bar-label mono">{v.slice(0, 4)}</span>
                    <div className="lp-demo-bar-track">
                      <div
                        className="lp-demo-bar-fill"
                        style={{
                          width: demoVis ? `${(verdicts[i] / 10) * 100}%` : '0%',
                          background: ['var(--true)', 'var(--false)', 'var(--partial)', 'var(--contested)', 'var(--unverifiable)'][i],
                          transitionDelay: `${0.3 + i * 0.08}s`,
                        }}
                      />
                    </div>
                    <span className="lp-demo-bar-count mono">{verdicts[i]}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── BONUS FEATURES ── */}
      <section className="lp-bonus">
        <div className="lp-section-head">
          <span className="lp-eyebrow mono">Bonus Capabilities</span>
          <h2 className="lp-section-title display">Beyond fact-checking.</h2>
        </div>
        <div className="lp-bonus-grid">
          <div className="lp-bonus-card">
            <div className="lp-bonus-icon" style={{ color: 'var(--accent)' }}>⊛</div>
            <h3 className="lp-bonus-title">AI Text Detection</h3>
            <p className="lp-bonus-desc">
              Four deterministic signals — sentence burstiness, length clustering,
              function-word density, and punctuation regularity — combine into a 0–100 AI origin probability score.
            </p>
          </div>
          <div className="lp-bonus-card">
            <div className="lp-bonus-icon" style={{ color: 'var(--contested)' }}>⊝</div>
            <h3 className="lp-bonus-title">Deepfake Detection <span className="wip-badge mono" style={{ fontSize: '10px', verticalAlign: 'middle', opacity: 0.6 }}>(work in progress)</span></h3>
            <p className="lp-bonus-desc">
              Images extracted from URL inputs are sent to the Hive AI API for deepfake
              and AI-generation analysis with per-image confidence scores.
            </p>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="lp-cta">
        <div className="lp-cta-glow" />
        <h2 className="lp-cta-title display">Ready to verify?</h2>
        <p className="lp-cta-sub">Paste text or drop a URL. Results in under 60 seconds.</p>
        <button className="lp-btn-primary lp-btn-lg" onClick={() => setPage('input')}>
          Start Analysing →
        </button>
      </section>

    </div>
  )
}