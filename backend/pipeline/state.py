from typing import TypedDict, List, Dict, Optional

class Claim(TypedDict):
    claim_id: int
    claim_text: str
    claim_type: str
    source_sentence: str

class Source(TypedDict):
    url: str
    title: str
    content_snippet: str
    domain: str
    authority_score: float
    publish_date: Optional[str]

class StructuredFact(TypedDict):
    source: str
    content: str

class EvidenceBundle(TypedDict):
    claim_id: int
    sources: List[Source]
    structured_facts: List[StructuredFact]
    queries_used: List[str]

class Verdict(TypedDict):
    claim_id: int
    verdict: str
    confidence: int
    cited_passage: str
    reasoning: str
    source_url: str
    jury_agreed: bool
    model_1_verdict: str
    model_2_verdict: str
    model_1_confidence: int
    model_2_confidence: int
    conflict_flag: bool
    self_reflection_critique: str
    critique_strength: int
    all_sources: List[Source]
    retry_count: int

class ConflictPair(TypedDict):
    claim_id: int
    claim_text: str
    source_a: Source
    source_b: Source
    source_a_summary: str
    source_b_summary: str
    better_supported: str

class MediaResult(TypedDict):
    url: str
    ai_generated_score: float
    is_deepfake: bool
    model_detected: Optional[str]
    error: Optional[str]

class AITextDetection(TypedDict):
    score: int
    label: str
    burstiness_signal: float
    uniformity_signal: float
    function_words_signal: float
    punctuation_signal: float
    # Legacy keys kept for backwards compatibility with cached reports
    perplexity_signal: float
    ngram_signal: float

class Report(TypedDict):
    session_id: str
    input_text: str
    word_count: int
    processed_at: str
    overall_trust_score: int
    claim_breakdown: Dict[str, int]
    claims: List[Dict]
    conflicts: List[ConflictPair]
    ai_text_detection: Optional[AITextDetection]
    media_detection: List[MediaResult]

class PipelineState(TypedDict):
    session_id: str
    input_text: str
    input_type: str
    original_url: Optional[str]
    word_count: int
    claims: List[Claim]
    evidence_bundles: Dict[int, EvidenceBundle]
    verdicts: Dict[int, Verdict]
    conflicts: List[ConflictPair]
    ai_text_detection: Optional[AITextDetection]
    media_results: List[MediaResult]
    report: Optional[Report]
    errors: List[str]
    iteration_count: int