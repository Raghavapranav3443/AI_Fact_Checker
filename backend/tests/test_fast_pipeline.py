import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.graph import run_pipeline, create_session, _sessions

async def main():
    sid = "test-session"
    create_session(sid)
    
    text = "Donald Trump is the President of the United States. He took office in January 2025. Also, the Earth orbits the Sun."
    
    print("Running pipeline...")
    await run_pipeline(
        session_id=sid,
        input_text=text,
        input_type="text",
        word_count=len(text.split()),
        opinion_flag=False
    )
    
    rep = _sessions[sid].get("report")
    if rep:
        print("PIPELINE SUCCESS")
        print("Claims:", len(rep.get("claims", [])))
        for c in rep.get("claims", []):
            print(f"- {c.get('claim_text')}: {c.get('verdict')} (Precision: {c.get('precision')}, Temporal Drift: {c.get('temporal_drift_flag')})")
    else:
        print("PIPELINE FAIL", _sessions[sid].get("errors"))

if __name__ == "__main__":
    asyncio.run(main())
