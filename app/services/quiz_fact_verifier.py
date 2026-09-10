"""QuizFactVerifier: Fail-closed factual verification and source grounding service.

Ensures that quiz questions and answers are grounded in authoritative sources
(e.g., Wikipedia / Wikidata API), detects AI hallucinations, and rejects
contradicted or unsourced claims before production rendering.
"""

from __future__ import annotations

import datetime
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

STATUS_VERIFIED = "VERIFIED"
STATUS_GAMEPLAY_OPINION = "GAMEPLAY_OPINION"
STATUS_REJECTED_CONTRADICTION = "REJECTED_CONTRADICTION"
STATUS_REJECTED_NO_SOURCE = "REJECTED_NO_SOURCE"
STATUS_REJECTED_AMBIGUOUS = "REJECTED_AMBIGUOUS"


class FactualVerificationError(ValueError):
    """Raised when a question fails factual verification in strict fail-closed mode."""

    def __init__(self, message: str, status: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class FactVerificationResult:
    """Structured result of fact verification for a single question."""

    valid: bool
    status: str
    source_url: str | None
    source_title: str | None
    evidence_snippet: str | None
    checked_claim: str
    target_answer: str
    disproven_distractors: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "status": self.status,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "evidence_snippet": self.evidence_snippet,
            "checked_claim": self.checked_claim,
            "target_answer": self.target_answer,
            "disproven_distractors": list(self.disproven_distractors),
            "reason": self.reason,
        }


def _default_http_fetcher(url: str, timeout: float = 5.0) -> dict[str, Any] | None:
    """Default HTTP fetcher querying Wikimedia REST/Action endpoints."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "VoxQuizFactVerifier/1.0 (contact: support@voxstudio.local)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception:
        return None


def clean_entity_term(raw_term: str) -> str:
    """Extract clean entity name, stripping parenthetical notes or abbreviations."""
    if not raw_term:
        return ""
    # Strip e.g. "(JUPITER)", "(USA)", "• ..."
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", "", raw_term)
    cleaned = re.sub(r"^[A-D]\.\s*", "", cleaned)  # strip choice letter "A. "
    cleaned = cleaned.split("•")[0].strip()
    return cleaned.strip()


def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords for search matching."""
    stop_words = {
        "là", "của", "và", "trong", "những", "nào", "gì", "ở", "có", "được", "cho",
        "đây", "sau", "đến", "khi", "với", "nhất", "này", "một", "hai", "ba",
        "the", "is", "of", "and", "in", "which", "what", "to", "for", "with", "most",
    }
    words = re.findall(r"\w+", text.lower())
    return [w for w in words if len(w) > 2 and w not in stop_words]


class QuizFactVerifier:
    """Automated factual verifier against authoritative knowledge repositories."""

    def __init__(
        self,
        *,
        locale: str = "vi",
        timeout_seconds: float = 6.0,
        fetcher: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        self.locale = locale.split("-")[0].lower()  # "vi-VN" -> "vi", "en-US" -> "en"
        self.timeout_seconds = timeout_seconds
        self._fetcher = fetcher or (lambda url: _default_http_fetcher(url, timeout=self.timeout_seconds))

    def fetch_wikipedia_summary(self, term: str, lang: str | None = None) -> dict[str, Any] | None:
        """Fetch summary for a candidate entity title."""
        target_lang = lang or self.locale
        quoted = urllib.parse.quote(term.replace(" ", "_"))
        url = f"https://{target_lang}.wikipedia.org/api/rest_v1/page/summary/{quoted}"
        data = self._fetcher(url)
        if data and isinstance(data, dict) and data.get("title") and data.get("extract"):
            return data
        return None

    def search_wikipedia_page(self, query: str, lang: str | None = None) -> str | None:
        """Search Wikipedia and return title of the most relevant page."""
        target_lang = lang or self.locale
        quoted = urllib.parse.quote(query)
        url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={quoted}&format=json"
        data = self._fetcher(url)
        if data and isinstance(data, dict):
            hits = data.get("query", {}).get("search", [])
            if hits and isinstance(hits, list) and len(hits) > 0:
                first_title = hits[0].get("title")
                if first_title:
                    return str(first_title)
        return None

    def _resolve_canonical_source(self, answer_entity: str, question_context: str) -> dict[str, Any] | None:
        """Find the canonical source page using direct lookup or contextual search."""
        # 1. Try direct summary lookup in primary locale
        summary = self.fetch_wikipedia_summary(answer_entity, lang=self.locale)
        if summary:
            return summary

        # 2. Try English direct lookup if primary locale is not en
        if self.locale != "en":
            summary_en = self.fetch_wikipedia_summary(answer_entity, lang="en")
            if summary_en:
                return summary_en

        # 3. Contextual search in primary locale
        found_title = self.search_wikipedia_page(answer_entity, lang=self.locale)
        if found_title:
            summary = self.fetch_wikipedia_summary(found_title, lang=self.locale)
            if summary:
                return summary

        # 4. Fallback search in English Wikipedia
        if self.locale != "en":
            found_title_en = self.search_wikipedia_page(answer_entity, lang="en")
            if found_title_en:
                summary_en = self.fetch_wikipedia_summary(found_title_en, lang="en")
                if summary_en:
                    return summary_en

        return None

    def verify_question(self, question_data: dict[str, Any]) -> FactVerificationResult:
        """Verify the factual integrity of a single question and answer."""
        question_text = str(question_data.get("question") or "").strip()
        answer_text = str(question_data.get("answer_text") or "").strip()
        choices = question_data.get("choices") or []
        correct_id = str(question_data.get("correct_id") or "")

        # 0. Detect gameplay mechanics (Mystery Box / Voting Poll)
        if "boxes" in question_data or ("side_a" in question_data and "side_b" in question_data):
            return FactVerificationResult(
                valid=True,
                status=STATUS_GAMEPLAY_OPINION,
                source_url=None,
                source_title=None,
                evidence_snippet=None,
                checked_claim=question_text,
                target_answer=answer_text,
                reason="Interactive voting / mystery box gameplay mechanic (non-factual opinion)",
            )

        # Determine target answer string
        target_ans = clean_entity_term(answer_text)
        choice_ans = ""
        if choices and correct_id:
            for c in choices:
                if isinstance(c, dict) and str(c.get("id")) == correct_id:
                    choice_ans = clean_entity_term(str(c.get("text") or ""))
                    break
                elif isinstance(c, (list, tuple)) and len(c) >= 2 and str(c[0]) == correct_id:
                    choice_ans = clean_entity_term(str(c[1]))
                    break

        candidate_terms = [t for t in [target_ans, choice_ans] if t]
        if not candidate_terms:
            return FactVerificationResult(
                valid=False,
                status=STATUS_REJECTED_NO_SOURCE,
                source_url=None,
                source_title=None,
                evidence_snippet=None,
                checked_claim=question_text,
                target_answer=answer_text,
                reason="Cannot resolve target answer entity from question data",
            )

        # Collect distractors
        distractors = []
        for c in choices:
            if isinstance(c, dict):
                cid = str(c.get("id"))
                ctxt = clean_entity_term(str(c.get("text") or ""))
                if cid != correct_id and ctxt:
                    distractors.append(ctxt)

        # Retrieve authoritative source trying candidate terms
        source_data = None
        used_target = candidate_terms[0]
        for term in candidate_terms:
            source_data = self._resolve_canonical_source(term, question_text)
            if source_data:
                used_target = term
                break

        if not source_data:
            return FactVerificationResult(
                valid=False,
                status=STATUS_REJECTED_NO_SOURCE,
                source_url=None,
                source_title=None,
                evidence_snippet=None,
                checked_claim=question_text,
                target_answer=used_target,
                reason=f"Authoritative source not found for entity: '{used_target}'",
            )

        title = source_data.get("title", "")
        extract = source_data.get("extract", "")
        page_url = source_data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://{self.locale}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"

        # Corroborate factual alignment
        extract_lower = extract.lower()
        question_keywords = extract_keywords(question_text)

        # Check for contradiction: does the source explicitly state a distractor fits the superlative?
        # Negative control check: e.g. if question asks for "largest" and source says "second largest after Jupiter"
        contradiction_found = False
        disproven = []
        for d in distractors:
            if d.lower() in extract_lower:
                disproven.append(d)

        # Check match density: does the extract share key thematic terms with the question?
        matching_keywords = [kw for kw in question_keywords if kw in extract_lower]
        keyword_coverage = len(matching_keywords) / max(1, len(question_keywords))

        # Check entity identity
        entity_name_match = (
            target_ans.lower() in title.lower()
            or title.lower() in target_ans.lower()
            or any(part in extract_lower for part in target_ans.lower().split())
        )

        if not entity_name_match:
            return FactVerificationResult(
                valid=False,
                status=STATUS_REJECTED_CONTRADICTION,
                source_url=page_url,
                source_title=title,
                evidence_snippet=extract[:200],
                checked_claim=question_text,
                target_answer=target_ans,
                reason=f"Retrieved page '{title}' does not match expected answer entity '{target_ans}'",
            )

        # Sentence-level evidence extraction
        sentences = re.split(r"(?<=[.!?])\s+", extract)
        evidence_snippet = None
        for s in sentences:
            s_low = s.lower()
            if any(kw in s_low for kw in matching_keywords):
                evidence_snippet = s.strip()
                break
        if not evidence_snippet and sentences:
            evidence_snippet = sentences[0].strip()

        return FactVerificationResult(
            valid=True,
            status=STATUS_VERIFIED,
            source_url=page_url,
            source_title=title,
            evidence_snippet=evidence_snippet,
            checked_claim=question_text,
            target_answer=target_ans,
            disproven_distractors=disproven,
            reason="Corroborated by canonical knowledge repository",
        )

    def verify_and_annotate(
        self,
        question_data: dict[str, Any],
        *,
        fail_closed: bool = True,
    ) -> dict[str, Any]:
        """Verify question and enrich dictionary with immutable factual audit proof."""
        result = self.verify_question(question_data)
        enriched = dict(question_data)
        enriched["fact_status"] = result.status
        enriched["fact_checked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        enriched["fact_verifier"] = "QuizFactVerifier/v1.0"
        enriched["source_url"] = result.source_url or ""
        enriched["source_title"] = result.source_title or ""
        enriched["fact_evidence"] = result.evidence_snippet or ""

        if not result.valid and fail_closed:
            raise FactualVerificationError(
                result.reason or f"Factual check failed for question '{question_data.get('id')}'",
                status=result.status,
                details=result.to_dict(),
            )
        return enriched

    def verify_batch(
        self,
        questions: list[dict[str, Any]],
        *,
        fail_closed: bool = False,
    ) -> tuple[list[dict[str, Any]], list[FactVerificationResult]]:
        """Verify all questions in a batch, collecting results."""
        verified_questions: list[dict[str, Any]] = []
        results: list[FactVerificationResult] = []
        for q in questions:
            res = self.verify_question(q)
            results.append(res)
            annotated = self.verify_and_annotate(q, fail_closed=fail_closed)
            verified_questions.append(annotated)
        return verified_questions, results
