import re

from config import now_ist

from pounce.models import AnswerMemoryRecord


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


class AnswerStore:
    """
    In-memory Q&A store populated from the server sync.
    Answers are looked up in scope priority: company → portal → global.
    New/updated answers are tracked for push back to the server.
    """

    def __init__(self, records: list[AnswerMemoryRecord]):
        self._records: list[AnswerMemoryRecord] = list(records)
        self._dirty: list[AnswerMemoryRecord] = []

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(
        self,
        question: str,
        company_domain: str | None = None,
        portal_key: str | None = None,
        confidence_threshold: float = 0.6,
    ) -> str | None:
        """
        Return the best stored answer for a question, or None.
        Tries company-scope first, then portal, then global.
        """
        key = _normalize(question)

        for scope_domain, scope_portal in [
            (company_domain, portal_key),    # company-specific
            (None, portal_key),              # portal-level
            (None, None),                    # global
        ]:
            answer = self._find(key, scope_domain, scope_portal, confidence_threshold)
            if answer is not None:
                return answer

        return None

    def _find(
        self,
        normalized_key: str,
        company_domain: str | None,
        portal_key: str | None,
        threshold: float,
    ) -> str | None:
        for rec in self._records:
            if rec.company_domain != company_domain:
                continue
            if rec.portal_key != portal_key:
                continue
            if rec.confidence < threshold:
                continue
            if rec.normalized_key == normalized_key:
                rec.use_count += 1
                rec.last_used = now_ist()
                return rec.answer
        return None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_answer(
        self,
        question_text: str,
        answer: str,
        field_type: str | None = None,
        options: list[str] | None = None,
        source: str = "llm",
        confidence: float = 0.7,
        company_domain: str | None = None,
        portal_key: str | None = None,
    ) -> AnswerMemoryRecord:
        key = _normalize(question_text)

        # Update if already in memory
        for rec in self._records:
            if (rec.normalized_key == key
                    and rec.company_domain == company_domain
                    and rec.portal_key == portal_key):
                rec.answer = answer
                rec.confidence = confidence
                rec.source = source
                rec.use_count += 1
                rec.last_used = now_ist()
                if rec not in self._dirty:
                    self._dirty.append(rec)
                return rec

        # Add new
        rec = AnswerMemoryRecord(
            question_text=question_text,
            normalized_key=key,
            answer=answer,
            field_type=field_type,
            options=options or [],
            source=source,
            confidence=confidence,
            company_domain=company_domain,
            portal_key=portal_key,
        )
        self._records.append(rec)
        self._dirty.append(rec)
        return rec

    def dirty_records(self) -> list[AnswerMemoryRecord]:
        """Return records that need to be pushed to the server."""
        return list(self._dirty)

    def clear_dirty(self) -> None:
        self._dirty.clear()

    # ------------------------------------------------------------------
    # Prompt context
    # ------------------------------------------------------------------

    def dump_for_prompt(
        self,
        company_domain: str | None = None,
        portal_key: str | None = None,
    ) -> str:
        """
        Return a compact string of known Q&A pairs for injection into the
        agent system prompt. Includes global + portal + company scopes.
        """
        lines = []
        seen_keys: set[str] = set()

        for scope_domain, scope_portal in [
            (company_domain, portal_key),
            (None, portal_key),
            (None, None),
        ]:
            for rec in self._records:
                if rec.company_domain != scope_domain:
                    continue
                if rec.portal_key != scope_portal:
                    continue
                if rec.normalized_key in seen_keys:
                    continue
                seen_keys.add(rec.normalized_key)
                lines.append(f'- "{rec.question_text}" → "{rec.answer}"')

        if not lines:
            return "(none)"
        return "\n".join(lines)
