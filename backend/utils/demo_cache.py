#!/usr/bin/env python3
"""
Demo Cache System — Rule E-1 from Agent Rules.

Run BEFORE the hackathon presentation:
  cd backend && venv/bin/python utils/demo_cache.py --build

During presentation if APIs fail, set in .env:
  DEMO_CACHE_MODE=true

The pipeline will return cached results instantly.
"""
import os, sys, json, asyncio, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

CACHE_DIR  = os.path.join(os.path.dirname(__file__), '..', 'demo_cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'scenarios.json')

# Three demo scenarios as specified in Block 10
DEMO_SCENARIOS = [
    {
        'id': 'scenario_1_mostly_true',
        'label': 'Mostly True — Well-sourced article',
        'type': 'text',
        'content': """The World Health Organization (WHO) was established on April 7, 1948, and is headquartered 
in Geneva, Switzerland. It is a specialized agency of the United Nations responsible for international 
public health. The WHO has 194 member states and employs approximately 8,000 people across its global offices.
The organization led the global response to the COVID-19 pandemic, which was declared a Public Health 
Emergency of International Concern in January 2020. The WHO's annual budget is approximately $6.7 billion 
for the 2022-2023 biennium. The organization was founded by 61 countries and its constitution came into 
force on April 7, which is now celebrated as World Health Day each year. The WHO Director-General is 
elected by the World Health Assembly for a five-year term. The current Director-General is Dr. Tedros 
Adhanom Ghebreyesus, who has served since 2017. The WHO plays a critical role in setting global health 
standards, coordinating responses to health emergencies, and supporting countries to strengthen their 
health systems."""
    },
    {
        'id': 'scenario_2_mixed',
        'label': 'Mixed Accuracy — Blog-style article with errors',
        'type': 'text',
        'content': """Artificial intelligence is transforming every industry at an unprecedented pace. 
OpenAI was founded in 2015 by Elon Musk and Sam Altman, among others, as a non-profit organization. 
The company released GPT-4 in March 2023, which many consider the most capable AI model ever created. 
Microsoft invested $13 billion in OpenAI in 2023. The global AI market is projected to reach $2 trillion 
by 2030 according to various analysts. Google's AI research division DeepMind, which was acquired for 
$500 million in 2014, created AlphaGo which defeated world champion Go player Lee Sedol in 2016. 
AlphaGo won all five matches in that series. Nvidia's market capitalization surpassed $3 trillion in 2024, 
making it briefly the most valuable company in the world. The company's H100 GPU chips are the primary 
hardware used to train large language models. China currently has more AI researchers than any other 
country, according to a 2023 report by Georgetown University's Center for Security and Emerging Technology."""
    },
    {
        'id': 'scenario_3_conflicting',
        'label': 'Conflicting Sources — Contested economic claims',
        'type': 'text',
        'content': """The global economy continues to show resilience despite significant headwinds. 
According to the International Monetary Fund, global GDP growth in 2023 was 3.1 percent, while the 
World Bank estimated slightly different figures. Inflation has been the primary challenge for central 
banks worldwide, with the United States Federal Reserve raising interest rates 11 times between 2022 
and 2023. The US unemployment rate fell to 3.4 percent in January 2023, its lowest level since 1969. 
China's GDP growth in 2023 was reported as 5.2 percent by Chinese government statistics, though some 
independent economists have questioned these figures. The European Union collectively represents the 
second largest economy in the world by nominal GDP. Germany entered a technical recession in 2023. 
The BRICS nations — Brazil, Russia, India, China, and South Africa — account for approximately 32 
percent of global GDP in purchasing power parity terms. Several new countries including Saudi Arabia, 
Iran, and the UAE joined the BRICS bloc in 2024."""
    }
]


async def build_cache():
    """Run all three demo scenarios through the full pipeline and cache results."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    from pipeline.graph import run_pipeline, get_session, create_session
    import uuid

    cached = {}
    for scenario in DEMO_SCENARIOS:
        print(f"\nBuilding cache for: {scenario['label']}")
        print(f"  Content: {len(scenario['content'].split())} words")

        session_id = str(uuid.uuid4())
        create_session(session_id)

        await run_pipeline(
            session_id=session_id,
            input_text=scenario['content'],
            input_type='text',
            word_count=len(scenario['content'].split()),
        )

        session = get_session(session_id)
        if session and session.get('status') == 'complete':
            report = session['report']
            cached[scenario['id']] = {
                'label':   scenario['label'],
                'report':  report,
                'content': scenario['content'],
            }
            trust = report.get('overall_trust_score', 0)
            claims_n = len(report.get('claims', []))
            conflicts_n = len(report.get('conflicts', []))
            print(f"  ✓ Cached: trust={trust}, claims={claims_n}, conflicts={conflicts_n}")
        else:
            errors = session.get('errors', []) if session else ['session not found']
            print(f"  ✗ Failed: {errors}")

    with open(CACHE_FILE, 'w') as f:
        json.dump(cached, f, indent=2, default=str)

    print(f"\n✓ Cache written to {CACHE_FILE}")
    print(f"  Scenarios cached: {len(cached)}/{len(DEMO_SCENARIOS)}")
    if len(cached) < 3:
        print("  WARNING: Not all scenarios cached — check API keys")
        sys.exit(1)
    else:
        print("  All scenarios cached. Demo is ready.\n")


def load_cached_report(scenario_id: str) -> dict | None:
    """Load a cached report. Used by pipeline when DEMO_CACHE_MODE=true."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
        return cached.get(scenario_id, {}).get('report')
    except Exception:
        return None


def list_scenarios():
    """Print available cached scenarios."""
    if not os.path.exists(CACHE_FILE):
        print("No cache file found. Run with --build first.")
        return
    with open(CACHE_FILE) as f:
        cached = json.load(f)
    print("\nCached demo scenarios:")
    for sid, data in cached.items():
        report = data.get('report', {})
        print(f"  [{sid}]")
        print(f"    Label:     {data.get('label')}")
        print(f"    Trust:     {report.get('overall_trust_score', '?')}/100")
        print(f"    Claims:    {len(report.get('claims', []))}")
        print(f"    Conflicts: {len(report.get('conflicts', []))}")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Veritas demo cache manager')
    parser.add_argument('--build', action='store_true', help='Build cache from live API calls')
    parser.add_argument('--list',  action='store_true', help='List cached scenarios')
    args = parser.parse_args()

    if args.build:
        asyncio.run(build_cache())
    elif args.list:
        list_scenarios()
    else:
        parser.print_help()
