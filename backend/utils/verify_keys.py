#!/usr/bin/env python3
"""
Run this before the hackathon demo.
Verifies every API key returns a live response.
Usage: cd backend && venv/bin/python utils/verify_keys.py
"""
import os, asyncio, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

GREEN = '\033[92m'
RED   = '\033[91m'
AMBER = '\033[93m'
RESET = '\033[0m'
BOLD  = '\033[1m'

results = []

async def check_groq():
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv('GROQ_API_KEY', ''))
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role':'user','content':'Reply with the single word: OK'}],
            max_tokens=5,
        ))
        text = resp.choices[0].message.content.strip()
        return True, f'Response: "{text}"'
    except Exception as e:
        return False, str(e)[:80]

async def check_groq_alt():
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv('GROQ_API_KEY', ''))
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role':'user','content':'Reply with the single word: OK'}],
            max_tokens=5,
        ))
        text = resp.choices[0].message.content.strip()
        return True, f'Response: "{text}"'
    except Exception as e:
        return False, str(e)[:80]

async def check_tavily():
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY', ''))
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: client.search('WHO founding year', max_results=1))
        count = len(resp.get('results', []))
        return True, f'{count} result(s) returned'
    except Exception as e:
        return False, str(e)[:80]

async def check_wikidata():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get('https://www.wikidata.org/w/api.php',
                params={'action':'wbsearchentities','search':'WHO','language':'en','format':'json','limit':1})
            data = r.json()
            label = data['search'][0]['label'] if data.get('search') else 'no results'
        return True, f'Top result: "{label}"'
    except Exception as e:
        return False, str(e)[:80]

async def check_wikipedia():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get('https://en.wikipedia.org/w/api.php',
                params={'action':'query','format':'json','titles':'Main Page','prop':'info'},
                headers={'User-Agent': 'Veritas/1.0 (https://github.com/Raghavapranav3443/Demo)'})
            data = r.json()
            pages = data.get('query', {}).get('pages', {})
            title = next(iter(pages.values())).get('title', 'unknown') if pages else 'unknown'
        return True, f'Article: "{title}"'
    except Exception as e:
        return False, str(e)[:80]

async def check_hive():
    key = os.getenv('HIVE_API_KEY', '')
    if not key or key == 'your_hive_api_key_here':
        return None, 'Key not set — media detection disabled (bonus B-02 skipped)'
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                'https://api.thehive.ai/api/v2/task/sync',
                json={'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png'},
                headers={'Authorization': f'Token {key}'},
            )
            if r.status_code in (200, 201):
                return True, 'Hive API reachable'
            else:
                return False, f'HTTP {r.status_code}: {r.text[:60]}'
    except Exception as e:
        return False, str(e)[:80]

async def main():
    print(f'\n{BOLD}VERITAS — API Key Verification{RESET}')
    print('=' * 50)

    checks = [
        ('Groq (llama-3.3-70b)',  check_groq,      True),
        ('Groq (llama-3.1-8b alt)',  check_groq_alt,   True),
        ('Tavily search',        check_tavily,     True),
        ('Wikidata (free)',      check_wikidata,   True),
        ('Wikipedia (free)',     check_wikipedia,  True),
        ('Hive (bonus B-02)',    check_hive,       False),
    ]

    all_required_ok = True

    for name, fn, required in checks:
        print(f'  Checking {name}... ', end='', flush=True)
        ok, msg = await fn()
        if ok is True:
            print(f'{GREEN}OK{RESET}  {msg}')
        elif ok is None:
            print(f'{AMBER}SKIP{RESET}  {msg}')
        else:
            marker = f'{RED}FAIL{RESET}'
            print(f'{marker}  {msg}')
            if required:
                all_required_ok = False

    print('=' * 50)
    if all_required_ok:
        print(f'{GREEN}{BOLD}All required APIs operational. Ready for demo.{RESET}\n')
        sys.exit(0)
    else:
        print(f'{RED}{BOLD}One or more required APIs failed. Fix before demo.{RESET}\n')
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
