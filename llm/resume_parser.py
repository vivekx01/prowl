from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

import config

_SYSTEM = """\
You are a professional career coach and technical recruiter. Given a candidate's resume text, \
produce a comprehensive, well-structured candidate profile in markdown. \
This profile is consumed by an AI system to evaluate job fit, so be precise and structured.

Include only sections for which data exists in the resume. Use this order:

## Professional Summary
2-3 sentences: who the candidate is, their primary domain, and what they're best suited for.

## Experience & Seniority
- Total years of professional experience
- Current / most recent role and company
- Seniority level with one-line justification: Junior / Mid / Senior / Staff / Principal / Lead

## Technical Skills
Group by category (include only non-empty groups):
- **Languages**:
- **Frameworks & Libraries**:
- **Databases**:
- **Cloud & Infrastructure**:
- **Tools & Platforms**:
- **Other**:

## Domain Experience
Industries, problem spaces, and types of systems the candidate has worked on.

## Role Preferences
Based on their trajectory, what types of roles align with their background? \
What kind of work are they best positioned for?

## Education
Degrees, institutions, graduation years, relevant certifications.

Rules:
- Do not invent information not present in the resume.
- Be specific with technologies — do not lump them as "various tools".
- Keep bullet points tight; avoid filler sentences.
"""


class ResumeParser:
    def __init__(self):
        self._llm = ChatOpenRouter(
            model=config.SCORE_MODEL,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.2,
        )

    async def generate_profile(self, resume_text: str) -> str:
        msgs = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Resume text:\n\n{resume_text}"),
        ]
        response = await self._llm.ainvoke(msgs)
        return response.content.strip()
