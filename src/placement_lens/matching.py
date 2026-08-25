"""Deterministic skill extraction for the first explainable baseline."""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple


SKILL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "python": ("python",),
    "sql": ("sql",),
    "power bi": ("power bi", "powerbi"),
    "scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "postgresql": ("postgresql", "postgres",),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure", "microsoft azure"),
    "gcp": ("gcp", "google cloud platform", "google cloud"),
    "excel": ("excel", "microsoft excel"),
    "etl": ("etl", "extract transform load", "extract, transform, load"),
    "kafka": ("kafka", "apache kafka"),
    "kubernetes": ("kubernetes", "k8s"),
    "docker": ("docker",),
    "git": ("git", "github", "gitlab"),
    "java": ("java",),
    "c++": ("c++", "cpp"),
    "matlab": ("matlab", "matlab app designer"),
    "linux": ("linux",),
    "data analysis": ("data analysis", "data analytics"),
    "exploratory data analysis": ("exploratory data analysis", "eda"),
    "correlation analysis": ("correlation analysis", "statistical correlation"),
    "data visualization": ("data visualization", "data visualisation"),
    "predictive analytics": ("predictive analytics", "predictive analysis"),
    "machine learning": ("machine learning",),
    "deep learning": ("deep learning",),
    "root cause analysis": ("root cause analysis", "rca"),
    "altium designer": ("altium designer", "altium"),
    "pcb design": ("pcb design", "printed circuit board design"),
    "embedded systems": ("embedded systems", "embedded system"),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "tensorflow": ("tensorflow", "tensor flow"),
    "xgboost": ("xgboost", "xg boost"),
    "spark": ("spark", "apache spark", "pyspark"),
    "databricks": ("databricks",),
    "snowflake": ("snowflake",),
    "dbt": ("dbt",),
    "airflow": ("airflow", "apache airflow"),
    "fastapi": ("fastapi", "fast api"),
    "streamlit": ("streamlit",),
    "mlflow": ("mlflow", "ml flow"),
    "hugging face": ("hugging face", "huggingface"),
    "nlp": ("nlp", "natural language processing"),
    "llm": ("llm", "llms", "large language model", "large language models"),
    "generative ai": ("generative ai", "genai", "gen ai"),
    "time series": ("time series", "time-series"),
    "forecasting": ("forecasting", "forecast"),
    "a/b testing": ("a/b testing", "a/b test", "ab testing", "ab test"),
    "pytorch": ("pytorch", "py torch"),
}


SKILL_WEIGHTS: Dict[str, float] = {
    "python": 2.0,
    "sql": 2.0,
    "machine learning": 2.0,
    "excel": 1.5,
    "aws": 1.5,
    "azure": 1.5,
    "gcp": 1.5,
    "etl": 1.5,
    "data analysis": 1.5,
    "statistics": 1.5,
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "using", "we", "will", "with", "you", "your",
}


@dataclass(frozen=True)
class CandidateProfile:
    skills: FrozenSet[str]
    target_levels: FrozenSet[str] = frozenset()
    preferred_title_terms: Tuple[str, ...] = ()
    profile_text: str = ""


@dataclass(frozen=True)
class JobPosting:
    job_id: str
    title: str
    company: str
    description: str
    location: str = ""
    levels: Tuple[str, ...] = ()
    source: str = ""
    source_url: str = ""
    published_at: str = ""
    timestamp_kind: str = "published"


@dataclass(frozen=True)
class MatchResult:
    score: float
    matched_skills: Tuple[str, ...]
    missing_skills: Tuple[str, ...]
    skill_coverage: float = 0.0
    skill_confidence: float = 0.0
    skill_score: float = 0.0
    title_score: float = 0.0
    text_score: float = 0.0
    level_score: float = 0.0


@dataclass(frozen=True)
class RankedJob:
    job: JobPosting
    match: MatchResult


def extract_skills(text: str) -> Set[str]:
    """Return canonical skill names found in free text."""
    normalized_text = text.casefold()
    found: Set[str] = set()

    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
            if re.search(pattern, normalized_text):
                found.add(canonical)
                break

    return found


def _tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9+#]+", text.casefold())
        if len(token) > 1 and token not in STOPWORDS
    ]


def _tfidf_similarities(query: str, documents: List[str]) -> List[float]:
    if not query.strip() or not documents:
        return [0.0 for _ in documents]

    counters = [Counter(_tokenize(text)) for text in [query] + documents]
    document_count = len(counters)
    document_frequency = Counter(
        token for counter in counters for token in counter.keys()
    )
    idf = {
        token: math.log((1 + document_count) / (1 + frequency)) + 1
        for token, frequency in document_frequency.items()
    }

    def vector(counter: Counter) -> Dict[str, float]:
        total = sum(counter.values()) or 1
        return {
            token: (count / total) * idf[token]
            for token, count in counter.items()
        }

    vectors = [vector(counter) for counter in counters]
    query_vector = vectors[0]
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scores: List[float] = []
    for document_vector in vectors[1:]:
        document_norm = math.sqrt(
            sum(value * value for value in document_vector.values())
        )
        if not query_norm or not document_norm:
            scores.append(0.0)
            continue
        dot_product = sum(
            value * document_vector.get(token, 0.0)
            for token, value in query_vector.items()
        )
        scores.append(round((dot_product / (query_norm * document_norm)) * 100, 1))
    return scores


def _advanced_match(
    candidate: CandidateProfile,
    job: JobPosting,
    *,
    text_score: float,
) -> MatchResult:
    required_skills = extract_skills(job.description)
    matched = candidate.skills & required_skills
    missing = required_skills - candidate.skills
    total_weight = sum(SKILL_WEIGHTS.get(skill, 1.0) for skill in required_skills)
    matched_weight = sum(SKILL_WEIGHTS.get(skill, 1.0) for skill in matched)
    skill_coverage = round((matched_weight / total_weight) * 100, 1) if total_weight else 0.0
    skill_confidence = round(min(1.0, len(required_skills) / 3) * 100, 1)
    skill_score = round(skill_coverage * (skill_confidence / 100), 1)

    normalized_title = job.title.casefold()
    title_score = (
        100.0
        if candidate.preferred_title_terms
        and any(term.casefold() in normalized_title for term in candidate.preferred_title_terms)
        else 0.0
    )
    level_score = (
        100.0
        if candidate.target_levels
        and candidate.target_levels.intersection(job.levels)
        else 0.0
    )
    score = round(
        0.55 * skill_score
        + 0.20 * title_score
        + 0.15 * text_score
        + 0.10 * level_score,
        1,
    )
    return MatchResult(
        score=score,
        matched_skills=tuple(sorted(matched)),
        missing_skills=tuple(sorted(missing)),
        skill_coverage=skill_coverage,
        skill_confidence=skill_confidence,
        skill_score=skill_score,
        title_score=title_score,
        text_score=text_score,
        level_score=level_score,
    )


def score_job(candidate: CandidateProfile, job: JobPosting) -> MatchResult:
    """Score a job by required-skill coverage and explain the result."""
    required_skills = extract_skills(job.description)
    matched = candidate.skills & required_skills
    missing = required_skills - candidate.skills
    score = (
        round((len(matched) / len(required_skills)) * 100, 1)
        if required_skills
        else 0.0
    )

    return MatchResult(
        score=score,
        matched_skills=tuple(sorted(matched)),
        missing_skills=tuple(sorted(missing)),
    )


def rank_jobs(
    candidate: CandidateProfile, jobs: Iterable[JobPosting]
) -> Tuple[RankedJob, ...]:
    """Rank jobs with legacy coverage or the advanced explainable model."""
    job_list = list(jobs)
    uses_advanced_model = bool(
        candidate.target_levels
        or candidate.preferred_title_terms
        or candidate.profile_text.strip()
    )
    if uses_advanced_model:
        text_scores = _tfidf_similarities(
            candidate.profile_text,
            [f"{job.title} {job.description}" for job in job_list],
        )
        ranked = [
            RankedJob(
                job=job,
                match=_advanced_match(candidate, job, text_score=text_score),
            )
            for job, text_score in zip(job_list, text_scores)
        ]
    else:
        ranked = [
            RankedJob(job=job, match=score_job(candidate, job))
            for job in job_list
        ]
    return tuple(sorted(ranked, key=lambda item: (-item.match.score, item.job.job_id)))
