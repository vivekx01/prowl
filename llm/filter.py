"""
Two-stage LLM filtering:
  Stage 1 — bulk candidate pass: given a list of job titles + metadata,
             ask a cheap model to pick the ones worth a closer look.
  Stage 2 — deep match: given the full JD + candidate profile,
             score the job and decide whether to apply.
"""

import json
import re
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, SystemMessage

import config
from scrapers.base import JobListing


def _parse_json(raw: str) -> dict:
    """Parse JSON that may be wrapped in markdown code fences."""
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Strip all bare control characters and retry. Safe because JSON
        # structural whitespace is optional, and control chars inside string
        # values must be escaped by the LLM anyway — \r→\n is still invalid.
        cleaned = re.sub(r'[\x00-\x1f]', '', raw)
        return json.loads(cleaned)


def _make_llm(model: str) -> ChatOpenRouter:
    return ChatOpenRouter(
        model=model,
        openrouter_api_key=config.OPENROUTER_API_KEY,
        temperature=0,
    )


def _extract_usage(response) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from a LangChain response."""
    meta = getattr(response, "usage_metadata", None)
    if meta:
        return meta.get("input_tokens", 0), meta.get("output_tokens", 0)
    token_usage = getattr(response, "response_metadata", {}).get("token_usage", {})
    return token_usage.get("prompt_tokens", 0), token_usage.get("completion_tokens", 0)


STAGE1_SYSTEM = """\
You are a job search assistant performing a fast, aggressive title-level filter to minimise wasted effort.

Given the candidate profile and a numbered list of job titles, return ONLY the indices of jobs \
that are plausibly worth a detailed review. Be strict — it is far better to drop a borderline job \
here than to waste tokens evaluating it in the next stage.

Use ONLY the job title (and location if relevant) to decide. Do NOT guess at the full JD.

Rules (all derived from the candidate profile — do not hardcode):
1. SENIORITY: Infer the candidate's level from their years of experience and current role. \
   Exclude titles that clearly indicate a level above what the candidate can reasonably target.
2. TECH STACK: If the title explicitly names a technology (language, framework, platform) that \
   is NOT in the candidate's skill set, exclude it. E.g. if title says "Java Engineer" or \
   "C++ Developer" and the candidate has neither, drop it immediately.
3. ROLE TYPE: Exclude roles that are clearly outside the candidate's domain based on their profile \
   (e.g. pure sales, pure research, QA/testing, non-engineering functions).
4. INCLUDE anything that looks like a plausible match — even if the title is vague. \
   Only exclude when there is a clear signal of mismatch.

Respond with a JSON object in this exact format:
{{"candidates": [1, 5, 12, ...]}}

No explanation, no markdown, just the JSON."""

STAGE1_USER_TMPL = """\
## Candidate Profile
{profile}

## Job Listings
{job_list}
"""


STAGE2_SYSTEM = """\
You are a precise job-fit evaluator. Given a candidate profile and a full job description, \
produce a calibrated score and verdict.

STEP 1 — Extract from the JD (do this mentally before scoring):
• Required years of experience and seniority level
• Must-have technical skills (explicitly required)
• Nice-to-have skills (preferred/bonus)
• Core day-to-day responsibilities

STEP 2 — Score each dimension out of 10:
  A. Technical fit   (35%): fraction of required skills possessed; bonus for preferred skills
  B. Seniority match (25%): candidate years/level vs JD requirement — penalise over/under by >2 years
  C. Role fit        (25%): day-to-day work alignment with candidate's background and goals
  D. Domain fit      (15%): industry/problem-space alignment

STEP 3 — Compute weighted score:
  score = round(A×0.35 + B×0.25 + C×0.25 + D×0.15, 1)

VERDICT:
  "apply"  — score ≥ 7.0 AND seniority is compatible (candidate not underqualified by more than 1 year)
  "skip"   — everything else

CALIBRATION (most jobs should land 4–7; be conservative, do not inflate):
  9.0–10.0  Exceptional — candidate exceeds requirements across the board
  7.5–8.9   Strong fit — minor gaps, clear case to apply
  6.0–7.4   Stretch — notable gaps but not disqualifying
  4.0–5.9   Weak — significant mismatch in stack or seniority
  1.0–3.9   Poor — wrong role type, wrong domain, or hard blockers present

Respond with this exact JSON and nothing else:
{{
  "score": <float 1.0–10.0, one decimal place>,
  "verdict": "apply" | "skip",
  "reason": "<2–3 sentences: what matches well, what the main gap is, why this verdict>"
}}"""

STAGE2_USER_TMPL = """\
## Candidate Profile
{profile}

## Job: {title} at {company}
{description}
"""


class JobFilter:
    def __init__(self, profile: str):
        self.profile = profile
        self._filter_llm = _make_llm(config.FILTER_MODEL)
        self._score_llm = _make_llm(config.SCORE_MODEL)
        self._input_tokens = 0
        self._output_tokens = 0

    @property
    def token_usage(self) -> tuple[int, int]:
        return self._input_tokens, self._output_tokens

    async def stage1_filter(self, listings: list[JobListing]) -> list[JobListing]:
        """Return subset of listings that pass the bulk title-level filter."""
        if not listings:
            return []

        numbered = "\n".join(
            f"{i+1}. {j.title} | {j.company} | {j.location}"
            for i, j in enumerate(listings)
        )

        messages = [
            SystemMessage(content=STAGE1_SYSTEM),
            HumanMessage(content=STAGE1_USER_TMPL.format(
                profile=self.profile,
                job_list=numbered,
            )),
        ]

        response = await self._filter_llm.ainvoke(messages)
        inp, out = _extract_usage(response)
        self._input_tokens += inp
        self._output_tokens += out
        raw = response.content.strip()

        try:
            parsed = _parse_json(raw)
            indices = [int(i) - 1 for i in parsed.get("candidates", [])]
            return [listings[i] for i in indices if 0 <= i < len(listings)]
        except Exception as e:
            print(f"  [llm] stage1 parse error: {e}")
            return listings  # fall through — don't drop everything on parse failure

    async def stage2_score(self, listing: JobListing) -> dict:
        """Score a single listing that already has description filled in."""
        messages = [
            SystemMessage(content=STAGE2_SYSTEM),
            HumanMessage(content=STAGE2_USER_TMPL.format(
                profile=self.profile,
                title=listing.title,
                company=listing.company,
                description=listing.description or "(no description available)",
            )),
        ]

        response = await self._score_llm.ainvoke(messages)
        inp, out = _extract_usage(response)
        self._input_tokens += inp
        self._output_tokens += out
        raw = response.content.strip()

        try:
            return _parse_json(raw)
        except Exception as e:
            print(f"  [llm] stage2 parse error for {listing.title}: {e}")
            print(f"  [llm] raw response was: {raw[:300]!r}")
            return None
