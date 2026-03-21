import React, { useState, useEffect, useRef } from 'react';
import { usePipelineContext } from '../context/PipelineContext';
import './LandingPage.css';

/* ── content ── */
const TECH_STACK = [
  { id: 'frontend', label: 'frontend', title: 'React & Vite', desc: 'Crafting a blazing-fast, responsive UI tailored for seamless interaction and instant feedback.' },
  { id: 'backend', label: 'backend', title: 'Python / Express', desc: 'Robust routing and secure data handling to orchestrate complex verification workflows.' },
  { id: 'llm', label: 'llm_core', title: 'Google Gemini', desc: 'State-of-the-art agentic processing for precision claim extraction and logical verification.' },
  { id: 'search', label: 'retrieval', title: 'Custom Search API', desc: 'Real-time, autonomous web integration traversing authoritative sources across the globe.' },
];

const FEATURES = [
  { sig: 'F-01', icon: '[TGT]', title: 'Automated Fact Extraction', desc: 'Intelligently decomposes complex essays and lengthy articles into discrete, atomic, verifiable statements.' },
  { sig: 'F-02', icon: '[NET]', title: 'Autonomous Retrieval', desc: 'Dynamically formulates multi-layered queries and cross-references live data from the web in real time.' },
  { sig: 'F-03', icon: '[VRF]', title: 'Granular Accuracy', desc: 'Strict TRUE / FALSE / PARTIAL classification with explicit citations and logical reasoning chains.' },
  { sig: 'F-04', icon: '[SHL]', title: 'Content Authenticity', desc: 'Detects AI-generated phrasing and synthetic media manipulation to ensure pure human integrity.' },
];

const PIPELINE_STEPS = [
  { cmd: '$ veritas extract', label: 'EXTRACT', desc: 'Upload document or URL. Agent isolates core verifiable claims while preserving original context.' },
  { cmd: '$ veritas search', label: 'SEARCH', desc: 'System queries real-world sources, retrieving relevant evidence and filtering out noise autonomously.' },
  { cmd: '$ veritas verify', label: 'VERIFY', desc: 'Evidence meets claim. Engine produces a detailed report citing exactly why a claim holds true or fails.' },
];

/* ── Matrix rain canvas ── */
function MatrixRain() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let w = canvas.width = window.innerWidth;
    let h = canvas.height = window.innerHeight;
    const cols = Math.floor(w / 20);
    const drops = Array(cols).fill(1);
    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノABCDEFVERITAS<>{}[]|/\\';

    function draw() {
      ctx.fillStyle = 'rgba(0,0,0,0.05)';
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = '#003B00';
      ctx.font = '14px monospace';
      drops.forEach((y, i) => {
        const ch = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillStyle = Math.random() > 0.97 ? '#00FF41' : '#003B00';
        ctx.fillText(ch, i * 20, y * 20);
        if (y * 20 > h && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      });
    }
    const id = setInterval(draw, 60);
    const resize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resize);
    return () => { clearInterval(id); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} className="matrix-canvas" />;
}

/* ── typewriter hook ── */
function useTypewriter(text, speed = 45, startDelay = 0) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  useEffect(() => {
    setDisplayed('');
    setDone(false);
    let i = 0;
    const start = setTimeout(() => {
      const id = setInterval(() => {
        i++;
        setDisplayed(text.slice(0, i));
        if (i >= text.length) { clearInterval(id); setDone(true); }
      }, speed);
      return () => clearInterval(id);
    }, startDelay);
    return () => clearTimeout(start);
  }, [text, speed, startDelay]);
  return [displayed, done];
}

/* ── glitch text ── */
function GlitchText({ text, className = '' }) {
  return (
    <span className={`glitch ${className}`} data-text={text}>
      {text}
    </span>
  );
}

/* ── terminal window wrapper ── */
function TermWindow({ title, children, className = '', style }) {
  return (
    <div className={`term-window ${className}`} style={style}>
      <div className="term-titlebar">
        <span className="term-dot term-dot--red" />
        <span className="term-dot term-dot--yellow" />
        <span className="term-dot term-dot--green" />
        <span className="term-title">{title}</span>
      </div>
      <div className="term-body">{children}</div>
    </div>
  );
}

/* ── scroll reveal hook ── */
function useReveal(threshold = 0.12) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVis(true); obs.disconnect(); } },
      { threshold }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, vis];
}

/* ════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ════════════════════════════════════════════════════════════ */
export default function LandingPage() {
  const { setPage } = usePipelineContext();
  const [activeTab, setActiveTab] = useState(0);
  const [bootLine, bootDone] = useTypewriter('INITIALIZING VERITAS v2.4.1 ...', 35, 200);
  const [statusLine,] = useTypewriter('> SYSTEM READY. ALL MODULES ONLINE.', 30, 1800);
  const [techRef, techVis] = useReveal();
  const [featRef, featVis] = useReveal();
  const [pipeRef, pipeVis] = useReveal();

  useEffect(() => {
    const id = setInterval(() => setActiveTab(p => (p + 1) % TECH_STACK.length), 4000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="lp-root">
      {/* scanline overlay */}
      <div className="scanlines" aria-hidden="true" />

      {/* ── HERO ──────────────────────────────────────────── */}
      <section className="lp-hero">
        <MatrixRain />

        <div className="lp-hero__content">
          {/* boot sequence */}
          <div className="boot-seq">
            <span className="boot-line">{bootLine}{!bootDone && <span className="cursor">█</span>}</span>
            {bootDone && <span className="boot-status">{statusLine}<span className="cursor">█</span></span>}
          </div>

          {/* ASCII banner */}
          <pre className="ascii-banner" aria-label="VERITAS">
            {`
 ██╗   ██╗███████╗██████╗ ██╗████████╗ █████╗ ███████╗
 ██║   ██║██╔════╝██╔══██╗██║╚══██╔══╝██╔══██╗██╔════╝
 ██║   ██║█████╗  ██████╔╝██║   ██║   ███████║███████╗
 ╚██╗ ██╔╝██╔══╝  ██╔══██╗██║   ██║   ██╔══██║╚════██║
  ╚████╔╝ ███████╗██║  ██║██║   ██║   ██║  ██║███████║
   ╚═══╝  ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝`}
          </pre>

          <p className="hero-tagline">
            <span className="prompt-sym">&gt;&gt;</span>
            &nbsp;FACT &amp; CLAIM VERIFICATION SYSTEM&nbsp;
            <span className="prompt-sym">&lt;&lt;</span>
          </p>

          <div className="hero-desc-block">
            <span className="line-num">01</span>
            <p className="hero-desc">
              In an era of AI hallucinations and rampant misinformation — secure your
              digital content with an agentic verification engine. Real-world cross-referencing.
              Automated claim extraction. Undeniable accuracy.
            </p>
          </div>

          <div className="hero-actions">
            <button className="hack-btn hack-btn--primary" onClick={() => setPage('input')}>
              <span className="hack-btn__prefix">root@veritas:~$</span>
              <span className="hack-btn__cmd">./launch --now</span>
            </button>
            <a href="#pipeline" className="hack-btn hack-btn--ghost">
              <span className="hack-btn__prefix">$</span>
              <span className="hack-btn__cmd">cat HOW_IT_WORKS.md</span>
            </a>
          </div>

          {/* status bar */}
          <div className="status-bar">
            <span className="status-item"><span className="status-dot status-dot--ok" />SYS_STATUS: ONLINE</span>
            <span className="status-sep">|</span>
            <span className="status-item">MODULES: 4/4 LOADED</span>
            <span className="status-sep">|</span>
            <span className="status-item">INTEGRITY: 100%</span>
            <span className="status-sep">|</span>
            <span className="status-item"><span className="status-dot status-dot--ok" />UPTIME: 99.97%</span>
          </div>
        </div>
      </section>

      {/* ── TECH STACK ────────────────────────────────────── */}
      <section className="lp-tech" ref={techRef}>
        <div className={`lp-tech__inner ${techVis ? 'is-visible' : ''}`}>
          <div className="section-label">
            <span className="section-label__line" />&nbsp;
            cat /etc/veritas/stack.conf
            &nbsp;<span className="section-label__line" />
          </div>

          <TermWindow title="stack.conf — architecture overview" className="tech-term">
            {/* sidebar index */}
            <div className="tech-layout">
              <div className="tech-index">
                {TECH_STACK.map((t, i) => (
                  <button
                    key={t.id}
                    className={`tech-index__item ${activeTab === i ? 'is-active' : ''}`}
                    onClick={() => setActiveTab(i)}
                  >
                    <span className="tech-index__num">[{String(i).padStart(2, '0')}]</span>
                    <span className="tech-index__lbl">{t.label}</span>
                    {activeTab === i && <span className="tech-index__arrow"> ▶</span>}
                  </button>
                ))}
              </div>

              <div className="tech-detail" key={activeTab}>
                <div className="tech-detail__path">
                  /modules/{TECH_STACK[activeTab].label}/config.json
                </div>
                <div className="tech-detail__block">
                  <span className="json-key">"module"</span>
                  <span className="json-colon">: </span>
                  <span className="json-str">"{TECH_STACK[activeTab].title}"</span>
                  <span className="json-comma">,</span>
                </div>
                <div className="tech-detail__block">
                  <span className="json-key">"status"</span>
                  <span className="json-colon">: </span>
                  <span className="json-ok">"ACTIVE"</span>
                  <span className="json-comma">,</span>
                </div>
                <div className="tech-detail__block">
                  <span className="json-key">"description"</span>
                  <span className="json-colon">: </span>
                  <span className="json-val">"{TECH_STACK[activeTab].desc}"</span>
                </div>
                <div className="tech-detail__progress">
                  <span className="progress-lbl">LOADING&nbsp;</span>
                  <span className="progress-bar"><span className="progress-fill" /></span>
                  <span className="progress-pct"> 100%</span>
                </div>
              </div>
            </div>
          </TermWindow>
        </div>
      </section>

      {/* ── FEATURES ──────────────────────────────────────── */}
      <section className="lp-feats" ref={featRef}>
        <div className="section-label">
          <span className="section-label__line" />&nbsp;
          ls -la /capabilities/
          &nbsp;<span className="section-label__line" />
        </div>

        <div className={`feats-grid ${featVis ? 'is-visible' : ''}`}>
          {FEATURES.map((f, i) => (
            <TermWindow
              key={i}
              title={`${f.sig} :: ${f.title.toLowerCase().replace(/ /g, '_')}.exe`}
              className="feat-card"
              style={{ '--delay': `${i * 0.12}s` }}
            >
              <div className="feat-sig">{f.icon}</div>
              <div className="feat-cmd">&gt; exec <span className="feat-name">{f.title}</span></div>
              <div className="feat-output">{f.desc}</div>
              <div className="feat-status">EXIT_CODE: <span className="feat-ok">0x00 OK</span></div>
            </TermWindow>
          ))}
        </div>
      </section>

      {/* ── PIPELINE ──────────────────────────────────────── */}
      <section className="lp-pipeline" id="pipeline" ref={pipeRef}>
        <div className="section-label">
          <span className="section-label__line" />&nbsp;
          ./veritas --help pipeline
          &nbsp;<span className="section-label__line" />
        </div>

        <TermWindow title="veritas — pipeline execution trace" className="pipeline-term">
          <div className={`pipeline-steps ${pipeVis ? 'is-visible' : ''}`}>
            {PIPELINE_STEPS.map((s, i) => (
              <div
                className="pipe-step"
                key={i}
                style={{ '--delay': `${i * 0.2}s` }}
              >
                <div className="pipe-step__header">
                  <span className="pipe-step__idx">STEP {i + 1}/{PIPELINE_STEPS.length}</span>
                  <span className="pipe-step__sep"> ───────── </span>
                  <span className="pipe-step__status">[DONE]</span>
                </div>
                <div className="pipe-step__cmd">{s.cmd}</div>
                <div className="pipe-step__label">// {s.label}</div>
                <div className="pipe-step__desc">{s.desc}</div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="pipe-step__connector">
                    &nbsp;&nbsp;│<br />
                    &nbsp;&nbsp;▼
                  </div>
                )}
              </div>
            ))}
          </div>
        </TermWindow>
      </section>

      {/* ── FOOTER ────────────────────────────────────────── */}
      <footer className="lp-footer">
        <div className="footer-ascii">
          <pre>{`╔═══════════════════════════════════════════════════════════╗
║            READY TO ELIMINATE UNCERTAINTY?                ║
║          ACCESS GRANTED. AWAITING YOUR COMMAND.           ║
╚═══════════════════════════════════════════════════════════╝`}</pre>
        </div>
        <button className="hack-btn hack-btn--primary hack-btn--lg" onClick={() => setPage('input')}>
          <span className="hack-btn__prefix">root@veritas:~$</span>
          <span className="hack-btn__cmd">./veritas --launch</span>
        </button>
        <p className="footer-copy">
          <span className="prompt-sym">$</span> echo "VERITAS © 2024 — ALL CLAIMS VERIFIED. ALL RIGHTS RESERVED."
        </p>
      </footer>
    </div>
  );
}
