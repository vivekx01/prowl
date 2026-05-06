"""
Two-stage LLM filtering:
  Stage 1 — bulk candidate pass: given a list of job titles + metadata,
             ask a cheap model to pick the ones worth a closer look.
  Stage 2 — deep match: given the full JD + candidate profile,
             score the job and decide whether to apply.
"""

import json
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, SystemMessage

import config
from scrapers.base import JobListing


def _parse_json(raw: str) -> dict:
    """Extract and parse the first JSON object from a model response.

    Handles code fences, preamble text, and trailing commentary by slicing
    from the first '{' to the last '}' before attempting to parse.
    """
    start = raw.find('{')
    end = raw.rfind('}')
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object found in response: {raw[:200]!r}")
    return json.loads(raw[start:end + 1])


def _make_llm(model: str) -> ChatOpenRouter:
    return ChatOpenRouter(
        model=model,
        openrouter_api_key=config.OPENROUTER_API_KEY,
        temperature=0,
    )


def _extract_usage(response) -> tuple[int, int, int]:
    """Return (input_tokens, output_tokens, cached_tokens) from a LangChain response."""
    meta = getattr(response, "usage_metadata", None)
    if meta:
        inp = meta.get("input_tokens", 0)
        out = meta.get("output_tokens", 0)
        # OpenRouter reports cached hits under several possible keys
        cached = (
            meta.get("cache_read_input_tokens", 0)
            or meta.get("cached_tokens", 0)
            or (meta.get("input_token_details") or {}).get("cache_read", 0)
        )
        return inp, out, cached
    token_usage = getattr(response, "response_metadata", {}).get("token_usage", {})
    return token_usage.get("prompt_tokens", 0), token_usage.get("completion_tokens", 0), 0


STAGE1_SYSTEM = """\
You are a job search assistant performing a fast, aggressive title-level filter to minimise wasted effort.

Given the candidate profile and a numbered list of job titles, return ONLY the indices of jobs \
that are plausibly worth a detailed review. Be strict — it is far better to drop a borderline job \
here than to waste tokens evaluating it in the next stage.

Use ONLY the job title (and location if relevant) to decide. Do NOT guess at the full JD.

Rules (all derived from the candidate profile — do not hardcode):
1. LOCATION: Exclude any job that is NOT based in India and NOT explicitly remote/WFH. \
   If the location field names a city or country outside India (e.g. "New York", "London", "US", "UK", \
   "Singapore") with no remote option, drop it immediately. When location is blank or ambiguous, keep it.
2. SENIORITY: Infer the candidate's level from their years of experience and current role. \
   Exclude titles that clearly indicate a level above what the candidate can reasonably target.
3. TECH STACK: If the title explicitly names a technology (language, framework, platform) that \
   is NOT in the candidate's skill set, exclude it. E.g. if title says "Java Engineer" or \
   "C++ Developer" and the candidate has neither, drop it immediately.
4. ROLE TYPE: Exclude roles that are clearly outside the candidate's domain based on their profile \
   (e.g. pure sales, pure research, QA/testing, non-engineering functions).
5. INCLUDE anything that looks like a plausible match — even if the title is vague. \
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
  A. Technical fit   (40%): fraction of required skills possessed; bonus for preferred skills. \
     This is the most important dimension — a strong technical match should anchor the score high \
     even if other dimensions are weaker.
  B. Role fit        (30%): day-to-day work alignment with candidate's background and goals
  C. Seniority match (20%): candidate years/level vs JD requirement. \
     IMPORTANT: JD experience requirements are frequently inflated/aspirational, especially in India. \
     A 1–2 year gap is normal and should not dominate the score. \
     Only penalise heavily (score ≤ 4) when the gap is 4+ years or the role is clearly senior/staff/principal level.
  D. Domain fit      (10%): industry/problem-space alignment

STEP 3 — Compute weighted score:
  score = round(A×0.40 + B×0.30 + C×0.20 + D×0.10, 1)

VERDICT:
  "apply"  — score ≥ 7.0 AND no hard blockers (e.g. completely wrong tech stack, wrong role type)
  "skip"   — everything else

CALIBRATION — use the full range, do not compress scores into a narrow band:
  9.0–10.0  Exceptional — candidate exceeds requirements across the board
  7.5–8.9   Strong fit — minor gaps, clear case to apply
  6.0–7.4   Reasonable match — candidate meets core technical requirements with some gaps
  4.0–5.9   Weak — significant mismatch in stack or seniority gap of 4+ years
  1.0–3.9   Poor — wrong role type, wrong domain, or hard blockers (e.g. Java role, candidate has no Java)

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

COMPRESS_PROMPT = """\
Extract exactly three things from this candidate profile and respond in one line.

Format: "<N> YOE · <stack> · <role type>"
Example: "4 YOE · Python, FastAPI, React, PostgreSQL · mid-level backend/full-stack"

Rules:
- YOE: total years of professional experience as a number
- stack: comma-separated technologies/languages, max 8, most important first
- role type: 3-5 words describing the target role (seniority + domain)

Profile:
{profile}"""


class JobFilter:
    def __init__(self, profile: str):
        self.profile = profile
        self._compact_profile = profile  # replaced by warm_up(); full profile is safe fallback
        self._filter_llm = _make_llm(config.FILTER_MODEL)
        self._score_llm = _make_llm(config.SCORE_MODEL)
        self._filter_input_tokens = 0
        self._filter_output_tokens = 0
        self._score_input_tokens = 0
        self._score_output_tokens = 0
        self._cached_tokens = 0  # populated only when the model reports cache hits

    @property
    def token_usage(self) -> tuple[int, int]:
        return (
            self._filter_input_tokens + self._score_input_tokens,
            self._filter_output_tokens + self._score_output_tokens,
        )

    @property
    def detailed_token_usage(self) -> dict:
        return {
            "filter_input":  self._filter_input_tokens,
            "filter_output": self._filter_output_tokens,
            "score_input":   self._score_input_tokens,
            "score_output":  self._score_output_tokens,
            "cached":        self._cached_tokens,
        }

    async def warm_up(self) -> None:
        """Use full profile directly for stage1 filtering — compact profile disabled."""
        self._compact_profile = self.profile

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
                profile=self._compact_profile,
                job_list=numbered,
            )),
        ]

        response = await self._filter_llm.ainvoke(messages)
        inp, out, _ = _extract_usage(response)
        self._filter_input_tokens += inp
        self._filter_output_tokens += out
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
        inp, out, cached = _extract_usage(response)
        self._score_input_tokens += inp
        self._score_output_tokens += out
        self._cached_tokens += cached
        raw = response.content.strip()

        try:
            return _parse_json(raw)
        except Exception as e:
            print(f"  [llm] stage2 parse error for {listing.title}: {e}")
            print(f"  [llm] raw response was: {raw[:300]!r}")
            return None
