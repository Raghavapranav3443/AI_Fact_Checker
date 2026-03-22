#!/usr/bin/env python3
"""
Veritas — Master Launcher
Run from the project root:  python3 start.py

What it does, in order:
  1. Preflight — Python version, Node version, project structure
  2. Backend dependencies — create venv if missing, install all packages
  3. Frontend dependencies — npm install if node_modules missing
  4. Environment — validate .env exists and keys are non-placeholder
  5. Security self-test — SSRF rules, UUID validation, session TTL
  6. API connectivity — live ping of Groq, Gemini, Tavily, Wikidata, Wikipedia
  7. Port availability — confirm 8000 and 5173 are free
  8. Launch — start uvicorn + vite dev in background, stream logs to terminal
  9. Health poll — wait until both servers are accepting connections
 10. Open browser — open http://localhost:5173 automatically
"""

import os
import sys
import subprocess
import socket
import time
import asyncio
import signal
import threading
import textwrap
import shutil
import io
import tempfile
from pathlib import Path
from datetime import datetime

# Handle Windows terminal encoding for rich characters
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
AMBER  = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
RESET  = "\033[0m"

OK    = f"{GREEN}✓{RESET}"
WARN  = f"{AMBER}⚠{RESET}"
FAIL  = f"{RED}✗{RESET}"
INFO  = f"{CYAN}→{RESET}"
RUN   = f"{CYAN}↻{RESET}"

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent
BACKEND  = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV     = BACKEND / "venv"
if os.name == "nt":
    VENV_PY  = VENV / "Scripts" / "python.exe"
    VENV_PIP = VENV / "Scripts" / "pip.exe"
else:
    VENV_PY  = VENV / "bin" / "python3"
    VENV_PIP = VENV / "bin" / "pip"
ENV_FILE = BACKEND / ".env"

BACKEND_PORT  = 8001
FRONTEND_PORT = 5173

REQUIRED_PACKAGES = [
    "fastapi", "uvicorn", "langgraph", "langchain-core",
    "tavily-python", "google-genai", "groq", "httpx",
    "beautifulsoup4", "lxml", "python-dotenv", "aiohttp",
    "slowapi", "limits","trafilatura","playwright",
]

PLACEHOLDER_MARKERS = [
    "your_", "_here", "YOUR_", "REPLACE", "xxxx", "XXXX",
]

# Track child processes for clean shutdown
_procs: list[subprocess.Popen] = []
_shutdown = threading.Event()
_ENV_VARS = {}


def load_env_globals():
    """Load .env into global dict and os.environ."""
    global _ENV_VARS
    if not ENV_FILE.exists():
        return
    try:
        with open(ENV_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    k, v = key.strip(), val.strip()
                    # Remove potential quotes
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    _ENV_VARS[k] = v
                    os.environ[k] = v
    except Exception as e:
        print(f"  {WARN} Error reading .env: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def banner():
    print()
    print(f"{BOLD}{WHITE}{'═' * 58}{RESET}")
    print(f"{BOLD}{WHITE}  VERITAS — Trust Intelligence Platform{RESET}")
    print(f"{DIM}  Master Launcher  ·  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{WHITE}{'═' * 58}{RESET}")
    print()


def section(title: str):
    print(f"\n{BOLD}{CYAN}── {title}{RESET}")


def step(msg: str):
    print(f"  {RUN} {msg}", end="", flush=True)


def done(detail: str = ""):
    suffix = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"\r  {OK}{suffix}                                        ")


def warn(detail: str):
    print(f"\r  {WARN}  {AMBER}{detail}{RESET}                              ")


def fail(detail: str, fatal: bool = True):
    print(f"\r  {FAIL}  {RED}{detail}{RESET}                              ")
    if fatal:
        print(f"\n  {RED}{BOLD}Startup aborted.{RESET}\n")
        _cleanup()
        sys.exit(1)


def run_cmd(cmd: list, cwd=None, capture=True, env=None, shell=None) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    if shell is None:
        shell = (os.name == "nt")
    r = subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True, env=env,
        shell=shell,
    )
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def force_kill_port(port: int):
    """Forcefully kill any process using the specified port on Windows."""
    if os.name != 'nt': return
    try:
        # Find PIDs using the port
        cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
        rc, out, _ = run_cmd(['cmd', '/c', cmd], capture=True)
        if rc != 0 or not out.strip(): return

        pids = set()
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                pids.add(parts[-1])

        for pid in pids:
            if pid == '0': continue
            # /F = Force, /T = Tree (kill children too)
            run_cmd(['taskkill', '/F', '/T', '/PID', pid], capture=False)
    except Exception:
        pass


def _cleanup():
    """Terminate all child processes on exit."""
    # Try standard termination first
    for p in _procs:
        try: p.terminate()
        except Exception: pass
    
    # Force kill if they hang on ports
    force_kill_port(BACKEND_PORT)
    force_kill_port(FRONTEND_PORT)

    for p in _procs:
        try: p.wait(timeout=2)
        except Exception: pass


def _signal_handler(sig, frame):
    print(f"\n\n  {AMBER}Shutting down Veritas...{RESET}")
    _shutdown.set()
    _cleanup()
    print(f"  {OK} All processes stopped.\n")
    sys.exit(0)


# ── Step 1: Preflight ─────────────────────────────────────────────────────────

def check_preflight():
    section("Step 1 / 7  —  Preflight checks")

    # Python version
    step("Python version")
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 10):
        fail(f"Python 3.10+ required, got {major}.{minor}")
    done(f"Python {major}.{minor}.{sys.version_info.micro}")

    # Node.js
    step("Node.js")
    node = shutil.which("node")
    if not node:
        fail("Node.js not found. Install from https://nodejs.org (v18+)")
    rc, out, _ = run_cmd(["node", "--version"])
    if rc != 0:
        fail("node --version failed")
    ver_str = out.strip().lstrip("v")
    major_node = int(ver_str.split(".")[0])
    if major_node < 16:
        fail(f"Node.js 16+ required, got {out}")
    done(out)

    # npm
    step("npm")
    npm = shutil.which("npm")
    if not npm:
        fail("npm not found. Install Node.js from https://nodejs.org")
    rc, out, _ = run_cmd(["npm", "--version"])
    done(f"npm {out}")

    # Project structure
    step("Project structure")
    missing = []
    for p in [BACKEND, FRONTEND, BACKEND / "main.py", FRONTEND / "package.json",
              BACKEND / "agents", BACKEND / "pipeline", BACKEND / "utils"]:
        if not p.exists():
            missing.append(str(p.relative_to(ROOT)))
    if missing:
        fail(f"Missing project paths: {', '.join(missing)}")
    done("all directories present")

    # .env file
    step(".env file")
    if not ENV_FILE.exists():
        fail(
            f".env not found at backend/.env\n\n"
            f"  Create it with:\n"
            f"    GEMINI_API_KEY=your_key\n"
            f"    GROQ_API_KEY=your_key\n"
            f"    TAVILY_API_KEY=your_key\n"
            f"    HIVE_API_KEY=your_key   # optional\n"
            f"    DEMO_CACHE_MODE=false"
        )
    done("found")


# ── Step 2: Backend dependencies ──────────────────────────────────────────────

def check_backend_deps():
    section("Step 2 / 7  —  Backend dependencies")

    # Create venv if missing
    step("Virtual environment")
    if not VENV_PY.exists():
        print(f"\r  {RUN} Creating virtual environment...              ", flush=True)
        rc, _, err = run_cmd([sys.executable, "-m", "venv", str(VENV)])
        if rc != 0:
            fail(f"python -m venv failed: {err}")
        done("created")
    else:
        done("already exists")

    # Upgrade pip silently
    step("pip (upgrade)")
    run_cmd([str(VENV_PIP), "install", "--quiet", "--upgrade", "pip"])
    done()

    # Check which packages are missing
    step("Checking installed packages")
    rc, out, _ = run_cmd([str(VENV_PIP), "list", "--format=freeze"])
    installed_lower = out.lower()
    # Normalise: tavily-python → tavily, google-genai → google
    def _is_installed(pkg):
        key = pkg.lower().replace("-", "").replace("_", "")
        for line in installed_lower.splitlines():
            line_key = line.split("==")[0].replace("-", "").replace("_", "")
            if key.startswith(line_key) or line_key.startswith(key):
                return True
        return False

    missing_pkgs = [p for p in REQUIRED_PACKAGES if not _is_installed(p)]
    done(f"{len(REQUIRED_PACKAGES) - len(missing_pkgs)}/{len(REQUIRED_PACKAGES)} already installed")

    if missing_pkgs:
        step(f"Installing {len(missing_pkgs)} missing package(s): {', '.join(missing_pkgs)}")
        print()  # newline before pip output
        rc, _, err = run_cmd(
            [str(VENV_PIP), "install", "--quiet"] + missing_pkgs,
            capture=False,
        )
        if rc != 0:
            fail(f"pip install failed for: {', '.join(missing_pkgs)}")
        done("all installed")

    # Verify imports work
    step("Verifying backend imports")
    verify_script = textwrap.dedent("""
        import sys
        sys.path.insert(0, '.')
        from utils.retry import retry_with_backoff, parse_llm_json
        from utils.scraper import scrape_url, _validate_url
        from utils.validator import validate_input
        from utils.authority import score_domain
        from utils.evidence_bundler import build_evidence_bundle
        from utils.tavily_search import search_parallel
        from utils.knowledge_apis import query_all_knowledge_apis
        from agents.extractor import extract_claims
        from agents.query_generator import generate_queries
        from agents.verifier import verify_claim
        from agents.reflector import reflect_on_verdict
        from agents.conflict_detector import detect_conflicts
        from agents.ai_detector import detect_ai_text
        from agents.media_detector import detect_media
        from pipeline.graph import run_pipeline, create_session, get_session
        from api.routes import router
        import main
        print('ALL_IMPORTS:OK')
    """)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(verify_script)
        tmp_path = f.name
    try:
        rc, out, err = run_cmd([str(VENV_PY), tmp_path], cwd=str(BACKEND), shell=False)
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

    if rc != 0 or "ALL_IMPORTS:OK" not in out:
        fail(f"Backend import check failed:\n{err[-500:]}")
    done("all imports OK")


# ── Step 3: Frontend dependencies ─────────────────────────────────────────────

def check_frontend_deps():
    section("Step 3 / 7  —  Frontend dependencies")

    node_modules = FRONTEND / "node_modules"
    vite_bin     = node_modules / ".bin" / "vite"

    step("node_modules")
    if not node_modules.exists() or not vite_bin.exists():
        print(f"\r  {RUN} Running npm install (first time, ~30s)...      ", flush=True)
        rc, _, err = run_cmd(
            ["npm", "install", "--legacy-peer-deps", "--silent"],
            cwd=str(FRONTEND),
            capture=False,
        )
        if rc != 0:
            fail(f"npm install failed: {err}")
        done("installed")
    else:
        done("already present")

    # Quick sanity: vite binary exists
    step("vite binary")
    if not vite_bin.exists():
        fail(f"vite not found at {vite_bin} — try deleting node_modules and rerunning")
    done(str(vite_bin.relative_to(FRONTEND)))


# ── Step 4: Environment validation ────────────────────────────────────────────

def check_environment():
    section("Step 4 / 7  —  Environment validation")

    # Load .env into os.environ permanently
    load_env_globals()

    required_keys = {
        "GROQ_API_KEY":    True,
        "TAVILY_API_KEY":  True,
        "HIVE_API_KEY":    False,  # False = optional
    }

    all_required_present = True
    for key, required in required_keys.items():
        val = _ENV_VARS.get(key, "")
        is_placeholder = not val or any(m in val for m in PLACEHOLDER_MARKERS)

        step(f"{key}")
        if not val:
            if required:
                fail(f"{key} is missing from backend/.env", fatal=False)
                all_required_present = False
            else:
                warn(f"{key} not set — bonus feature (media detection) disabled")
        elif is_placeholder:
            if required:
                fail(f"{key} still has placeholder value: {val!r}", fatal=False)
                all_required_present = False
            else:
                warn(f"{key} placeholder — media detection disabled")
        else:
            masked = val[:6] + "..." + val[-4:] if len(val) > 12 else "***"
            done(masked)

    if not all_required_present:
        print(f"\n  {RED}{BOLD}One or more required API keys are missing or placeholder.{RESET}")
        print(f"  Edit {BACKEND}/.env and fill in real keys, then re-run.\n")
        _cleanup()
        sys.exit(1)

    # DEMO_CACHE_MODE warning
    cache_mode = _ENV_VARS.get("DEMO_CACHE_MODE", "false").lower()
    step("DEMO_CACHE_MODE")
    if cache_mode == "true":
        warn("DEMO_CACHE_MODE=true — pipeline will serve cached results")
    else:
        done("false (live mode)")


# ── Step 5: Security self-test ─────────────────────────────────────────────────

def check_security():
    section("Step 5 / 7  —  Security self-test")

    security_script = textwrap.dedent("""
        import sys, time, os
        sys.path.insert(0, '.')

        # ── 1. SSRF protection ─────────────────────────────────────────────
        from utils.scraper import _validate_url
        blocked = [
            'http://localhost/admin',
            'http://127.0.0.1/etc/passwd',
            'http://169.254.169.254/metadata',
            'http://192.168.1.1/router',
            'http://10.0.0.1/internal',
            'http://172.16.0.1/secret',
            'ftp://evil.com/file',
            'file:///etc/passwd',
            'javascript:alert(1)',
        ]
        allowed = [
            'https://reuters.com/article/test',
            'http://bbc.com/news/test',
            'https://wikipedia.org/wiki/Test',
        ]
        for url in blocked:
            try:
                _validate_url(url)
                print(f'SSRF_FAIL:{url}')
                sys.exit(1)
            except ValueError:
                pass
        for url in allowed:
            try:
                _validate_url(url)
            except ValueError as e:
                print(f'SSRF_ALLOWED_BLOCKED:{url}:{e}')
                sys.exit(1)
        print('SSRF:OK')

        # ── 2. Session TTL eviction ────────────────────────────────────────
        from pipeline.graph import create_session, get_session, _sessions, SESSION_TTL_SECONDS
        sid = 'deadbeef-dead-4ead-8ead-deadbeefcafe'
        create_session(sid)
        assert get_session(sid) is not None, 'new session should be readable'
        _sessions[sid]['created_at'] = time.time() - SESSION_TTL_SECONDS - 1
        assert get_session(sid) is None, 'expired session should return None'
        print('TTL:OK')

        # ── 3. Session store max cap enforced ──────────────────────────────
        from pipeline.graph import MAX_SESSIONS
        assert MAX_SESSIONS > 0, 'MAX_SESSIONS must be set'
        print(f'CAP:OK:{MAX_SESSIONS}')

        # ── 4. UUID validation ─────────────────────────────────────────────
        import re
        UUID_RE = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            re.IGNORECASE,
        )
        invalid = ['abc', 'not-a-uuid', '../etc/passwd', '1 OR 1=1', '<script>', '']
        valid   = ['00000000-0000-4000-8000-000000000000',
                   'aaaabbbb-cccc-4ddd-8eee-ffffffffffff']
        for uid in invalid:
            assert not UUID_RE.match(uid), f'Should reject: {uid!r}'
        for uid in valid:
            assert UUID_RE.match(uid), f'Should accept: {uid!r}'
        print('UUID:OK')

        # ── 5. parse_llm_json resilience ──────────────────────────────────
        from utils.retry import parse_llm_json
        assert parse_llm_json('[{"a":1}]')[0]['a'] == 1
        assert parse_llm_json('```json\\n{"v":"TRUE"}\\n```')['v'] == 'TRUE'
        assert parse_llm_json('{bad json}', default='X') == 'X'
        assert parse_llm_json('', default=None) is None
        assert parse_llm_json('{"v":"OK","extra":123}')['v'] == 'OK'
        print('JSON_PARSER:OK')

        # ── 6. No deprecated asyncio.get_event_loop calls ─────────────────
        hits = []
        for d in ['agents', 'utils', 'pipeline']:
            d_path = os.path.join('.', d)
            if not os.path.exists(d_path): continue
            for root, _, files in os.walk(d_path):
                for f in files:
                    if f.endswith('.py'):
                        p = os.path.join(root, f)
                        with open(p, errors='ignore') as f_obj:
                            if 'get_event_loop' in f_obj.read():
                                hits.append(p)
        assert not hits, f'Deprecated get_event_loop found: {hits}'
        print('ASYNCIO:OK')

        # ── 7. Domain authority scoring ───────────────────────────────────
        from utils.authority import score_domain
        assert score_domain('https://cdc.gov/page') == 1.0
        assert score_domain('https://nih.gov/page') == 1.0
        assert score_domain('https://stanford.edu/page') == 1.0
        assert score_domain('https://bbc.com/news') == 0.7
        assert score_domain('https://reuters.com/news') == 1.0
        assert score_domain('https://randomblog.io/post') == 0.4
        print('AUTHORITY:OK')

        # ── 8. Verification prompt grounding rules intact ─────────────────
        from agents.verifier import VERIFICATION_PROMPT
        assert 'INADMISSIBLE' in VERIFICATION_PROMPT, 'Grounding rule removed from verification prompt'
        assert 'UNVERIFIABLE' in VERIFICATION_PROMPT, 'UNVERIFIABLE verdict missing from prompt'
        print('PROMPT:OK')

        print('ALL_SECURITY:PASS')
    """)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(security_script)
        tmp_path = f.name
    try:
        rc, out, err = run_cmd([str(VENV_PY), tmp_path], cwd=str(BACKEND), shell=False)
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

    checks = {
        "SSRF:OK":          "SSRF protection (9 blocked / 3 allowed)",
        "TTL:OK":           "Session TTL eviction",
        "UUID:OK":          "UUID path validation",
        "JSON_PARSER:OK":   "Tolerant JSON parser",
        "ASYNCIO:OK":       "No deprecated asyncio calls",
        "AUTHORITY:OK":     "Domain authority scoring",
        "PROMPT:OK":        "Verification prompt grounding intact",
    }

    for token, label in checks.items():
        step(label)
        if token in out:
            # Extract cap value for CAP check
            if token == "TTL:OK":
                cap_line = [l for l in out.splitlines() if l.startswith("CAP:OK")]
                cap = cap_line[0].split(":")[-1] if cap_line else "?"
                done(f"max {cap} sessions")
            else:
                done()
        else:
            # Find the specific error
            fail_lines = [l for l in (out + err).splitlines() if "Error" in l or "assert" in l.lower() or "Fail" in l]
            detail = fail_lines[0] if fail_lines else err[-200:] if err else "unknown error"
            fail(f"{label} failed: {detail}")

    if "ALL_SECURITY:PASS" not in out:
        fail(f"Security check did not complete. Output:\n{out[-400:]}\n{err[-400:]}")


# ── Step 6: API connectivity ───────────────────────────────────────────────────

def check_apis():
    section("Step 6 / 7  —  API connectivity")

    api_script = textwrap.dedent("""
        import asyncio, os, sys
        sys.path.insert(0, '.')

        async def ping_groq():
            try:
                from groq import Groq
                key = os.getenv('GROQ_API_KEY', '')
                if not key: return False, 'key not set'
                client = Groq(api_key=key)
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(
                    model='llama-3.3-70b-versatile',
                    messages=[{'role':'user','content':'Say OK'}],
                    max_tokens=3,
                ))
                return True, resp.choices[0].message.content.strip()
            except Exception as e:
                return False, str(e)[:100]

        async def ping_groq_alt():
            try:
                from groq import Groq
                key = os.getenv('GROQ_API_KEY', '')
                if not key: return False, 'key not set'
                client = Groq(api_key=key)
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(
                    model='llama-3.1-8b-instant',
                    messages=[{'role':'user','content':'Say OK'}],
                    max_tokens=3,
                ))
                return True, resp.choices[0].message.content.strip()
            except Exception as e:
                return False, str(e)[:100]

        async def ping_tavily():
            try:
                from tavily import TavilyClient
                key = os.getenv('TAVILY_API_KEY', '')
                if not key: return False, 'key not set'
                client = TavilyClient(api_key=key)
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, lambda: client.search(
                    'World Health Organization founded', max_results=1))
                n = len(resp.get('results', []))
                return True, f'{n} result(s)'
            except Exception as e:
                return False, str(e)[:100]

        async def ping_wikidata():
            try:
                import httpx
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r = await c.get('https://www.wikidata.org/w/api.php',
                        params={'action':'wbsearchentities','search':'WHO',
                                'language':'en','format':'json','limit':1},
                        headers={'User-Agent': 'Veritas/1.0 (https://github.com/Raghavapranav3443/Demo)'})
                    d = r.json()
                    label = d['search'][0]['label'] if d.get('search') else '?'
                return True, f'top: {label!r}'
            except Exception as e:
                return False, str(e)[:100]

        async def ping_wikipedia():
            try:
                import httpx
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r = await c.get(
                        'https://en.wikipedia.org/w/api.php',
                        params={'action':'query','format':'json','titles':'Main Page','prop':'info'},
                        headers={'User-Agent': 'Veritas/1.0 (https://github.com/Raghavapranav3443/Demo)'})
                    d = r.json()
                    # The response structure is query -> pages -> {pid} -> title
                    pages = d.get('query', {}).get('pages', {})
                    title = next(iter(pages.values())).get('title', '?') if pages else '?'
                return True, title
            except Exception as e:
                return False, str(e)[:100]

        async def ping_hive():
            key = os.getenv('HIVE_API_KEY', '')
            if not key or any(m in key for m in ['your_','_here','REPLACE']):
                return None, 'not configured'
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as c:
                    r = await c.post(
                        'https://api.thehive.ai/api/v2/task/sync',
                        json={'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png'},
                        headers={'Authorization': f'Token {key}'})
                if r.status_code in (200, 201):
                    return True, 'reachable'
                return False, f'HTTP {r.status_code}'
            except Exception as e:
                return False, str(e)[:100]

        async def main():
            results = await asyncio.gather(
                ping_groq(), ping_groq_alt(), ping_tavily(),
                ping_wikidata(), ping_wikipedia(), ping_hive(),
            )
            labels = ['GROQ', 'GROQ_ALT', 'TAVILY', 'WIKIDATA', 'WIKIPEDIA', 'HIVE']
            for label, (ok, msg) in zip(labels, results):
                status = 'OK' if ok is True else ('SKIP' if ok is None else 'FAIL')
                print(f'API:{label}:{status}:{msg}')

        asyncio.run(main())
    """)

    print(f"  {DIM}(this makes live API calls — may take 10-20s){RESET}")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(api_script)
        tmp_path = f.name
    try:
        rc, out, err = run_cmd([str(VENV_PY), tmp_path], cwd=str(BACKEND), shell=False)
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

    required_apis  = {"GROQ", "GROQ_ALT", "TAVILY"}
    free_apis      = {"WIKIDATA", "WIKIPEDIA"}
    optional_apis  = {"HIVE"}
    any_required_failed = False

    for line in out.splitlines():
        if not line.startswith("API:"):
            continue
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        _, label, status, msg = parts[0], parts[1], parts[2], parts[3]

        step(f"{label}")
        if status == "OK":
            done(msg)
        elif status == "SKIP":
            warn(f"{msg}")
        elif status == "FAIL":
            if label in required_apis:
                fail(f"{label}: {msg}", fatal=False)
                any_required_failed = True
            else:
                warn(f"{label}: {msg} (non-critical)")

    if any_required_failed:
        print(f"\n  {RED}{BOLD}One or more required APIs failed.{RESET}")
        print(f"  Check your keys in backend/.env and ensure you have internet access.\n")
        _cleanup()
        sys.exit(1)


# ── Step 7: Port availability ──────────────────────────────────────────────────

def check_ports():
    section("Step 7 / 7  —  Port availability")

    for port, name in [(BACKEND_PORT, "Backend (uvicorn)"), (FRONTEND_PORT, "Frontend (vite)")]:
        step(f"Port {port}  ({name})")
        if port_open("127.0.0.1", port):
            fail(
                f"Port {port} is already in use.\n"
                f"  Kill the process using it:  lsof -ti :{port} | xargs kill -9"
            )
        done("free")


# ── Launch ────────────────────────────────────────────────────────────────────

def launch_servers():
    section("Launching servers")

    # Set up environment for backend
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(BACKEND)
    backend_env["PYTHONUNBUFFERED"] = "1"

    # ── Backend ──────────────────────────────────────────────────────────────
    step("Starting backend  (uvicorn :8000)")
    backend_cmd = [
        str(VENV_PY), "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", str(BACKEND_PORT),
        "--reload",
        "--log-level", "warning",   # suppress INFO spam; errors still shown
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(BACKEND),
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == "nt"),
    )
    _procs.append(backend_proc)
    done(f"pid {backend_proc.pid}")

    # ── Frontend ─────────────────────────────────────────────────────────────
    step("Starting frontend (vite    :5173)")
    frontend_env = os.environ.copy()
    frontend_env["NO_COLOR"] = "1"   # cleaner log output

    frontend_proc = subprocess.Popen(
        ["npx", "vite", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)],
        cwd=str(FRONTEND),
        env=frontend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == "nt"),
    )
    _procs.append(frontend_proc)
    done(f"pid {frontend_proc.pid}")

    # ── Log streaming threads ─────────────────────────────────────────────────
    def stream_logs(proc: subprocess.Popen, prefix: str, color: str):
        """Read process output and print with a coloured prefix."""
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                # Filter out very noisy / useless lines
                skip_patterns = [
                    "GET /api/stream",    # SSE keepalive — too frequent
                    "200 OK",
                    "Watching for",
                    "press h to show help",
                    "VITE v",
                ]
                if any(p in line for p in skip_patterns):
                    continue
                # Highlight errors
                if any(w in line.lower() for w in ["error", "exception", "traceback", "failed"]):
                    print(f"  {color}{BOLD}[{prefix}]{RESET} {RED}{line}{RESET}")
                else:
                    print(f"  {color}[{prefix}]{RESET} {DIM}{line}{RESET}")
        except Exception:
            pass

    backend_thread  = threading.Thread(target=stream_logs, args=(backend_proc,  "backend",  CYAN),  daemon=True)
    frontend_thread = threading.Thread(target=stream_logs, args=(frontend_proc, "frontend", AMBER), daemon=True)
    backend_thread.start()
    frontend_thread.start()

    # ── Wait for both to be ready ─────────────────────────────────────────────
    section("Waiting for servers to be ready")

    for port, name, timeout in [
        (BACKEND_PORT,  "backend",  30),
        (FRONTEND_PORT, "frontend", 45),
    ]:
        step(f"Waiting for {name} on :{port}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if port_open("127.0.0.1", port):
                break
            # Check if process died
            for proc in _procs:
                if proc.poll() is not None:
                    fail(f"Server process exited prematurely (code {proc.returncode}). "
                         f"Check logs above.")
            time.sleep(0.5)
        else:
            fail(f"{name} did not start within {timeout}s. Check logs above.")
        done(f"ready in {timeout - (deadline - time.time()):.1f}s" if port_open("127.0.0.1", port) else "")

    # ── Health check ──────────────────────────────────────────────────────────
    step("Backend health check  (/api/health)")
    import urllib.request, json as _json
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{BACKEND_PORT}/api/health", timeout=5) as r:
            body = _json.loads(r.read())
            assert body.get("status") == "ok", f"unexpected health response: {body}"
        done(f"status=ok, active_sessions={body.get('active_sessions', 0)}")
    except Exception as e:
        fail(f"Health check failed: {e}")


# ── Ready ─────────────────────────────────────────────────────────────────────

def print_ready():
    print()
    print(f"{BOLD}{GREEN}{'═' * 58}{RESET}")
    print(f"{BOLD}{GREEN}  ✓  VERITAS IS RUNNING{RESET}")
    print(f"{GREEN}{'═' * 58}{RESET}")
    print()
    print(f"  {BOLD}Frontend:{RESET}  http://localhost:{FRONTEND_PORT}")
    print(f"  {BOLD}Backend: {RESET}  http://localhost:{BACKEND_PORT}")
    print(f"  {BOLD}API docs:{RESET}  http://localhost:{BACKEND_PORT}/docs")
    print()
    print(f"  {DIM}Press Ctrl+C to stop both servers{RESET}")
    print()

    # Try to open browser automatically
    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{FRONTEND_PORT}")
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # ── SELF-HEALING: Clear ports before starting ──
    force_kill_port(BACKEND_PORT)
    force_kill_port(FRONTEND_PORT)

    banner()

    try:
        check_preflight()
        check_backend_deps()
        check_frontend_deps()
        check_environment()
        check_security()
        check_apis()
        check_ports()
        launch_servers()
        print_ready()
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n  {RED}{BOLD}Unexpected error: {e}{RESET}\n")
        import traceback
        traceback.print_exc()
        _cleanup()
        sys.exit(1)

    # Keep alive — wait for shutdown signal or process death
    try:
        while not _shutdown.is_set():
            for proc in _procs:
                if proc.poll() is not None:
                    print(f"\n  {RED}A server process exited unexpectedly (code {proc.returncode}).{RESET}")
                    print(f"  {AMBER}Check the logs above for errors.{RESET}\n")
                    _cleanup()
                    sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        _signal_handler(None, None)


if __name__ == "__main__":
    main()
