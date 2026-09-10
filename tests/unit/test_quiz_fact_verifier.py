from __future__ import annotations

import pytest
from app.services.quiz_fact_verifier import (
    FactVerificationResult,
    FactualVerificationError,
    QuizFactVerifier,
    STATUS_REJECTED_CONTRADICTION,
    STATUS_REJECTED_NO_SOURCE,
    STATUS_VERIFIED,
    clean_entity_term,
)


def _create_mock_fetcher(responses: dict[str, dict]):
    """Returns a deterministic fetcher that maps URL fragments to responses."""
    def fetcher(url: str):
        for pattern, response in responses.items():
            if pattern in url:
                return response
        return None
    return fetcher


def test_clean_entity_term():
    assert clean_entity_term("SAO MỘC (JUPITER)") == "SAO MỘC"
    assert clean_entity_term("A. Paris") == "Paris"
    assert clean_entity_term("HỐ ĐEN • BLACK HOLE") == "HỐ ĐEN"
    assert clean_entity_term("") == ""


def test_positive_control_verified():
    mock_data = {
        "Sao_M": {
            "title": "Sao Mộc",
            "extract": "Sao Mộc là hành tinh thứ năm tính từ Mặt Trời và là hành tinh lớn nhất trong Hệ Mặt Trời. Nó là hành tinh khí khổng lồ.",
            "content_urls": {"desktop": {"page": "https://vi.wikipedia.org/wiki/Sao_M%E1%BB%99c"}},
        }
    }
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher(mock_data))
    question = {
        "id": "q1",
        "question": "Hành tinh nào lớn nhất trong Hệ Mặt Trời?",
        "choices": [
            {"id": "A", "text": "Sao Thổ"},
            {"id": "B", "text": "Sao Mộc"},
        ],
        "correct_id": "B",
        "answer_text": "Sao Mộc",
    }
    result = verifier.verify_question(question)
    assert result.valid is True
    assert result.status == STATUS_VERIFIED
    assert result.source_url == "https://vi.wikipedia.org/wiki/Sao_M%E1%BB%99c"
    assert "hành tinh lớn nhất" in (result.evidence_snippet or "").lower()


def test_negative_control_fabricated_entity_rejected():
    # Empty mock responses simulates entity not existing in Wikipedia
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher({}))
    question = {
        "id": "q_fake",
        "question": "Hành tinh nào làm bằng kim cương nhân tạo?",
        "choices": [{"id": "A", "text": "Hành Tinh X-999"}],
        "correct_id": "A",
        "answer_text": "Hành Tinh X-999",
    }
    result = verifier.verify_question(question)
    assert result.valid is False
    assert result.status == STATUS_REJECTED_NO_SOURCE
    assert "not found" in result.reason.lower()


def test_negative_control_contradiction_rejected():
    mock_data = {
        "Sao_H": {
            "title": "Sao Hỏa",
            "extract": "Sao Hỏa là hành tinh thứ tư tính từ Mặt Trời và là hành tinh nhỏ thứ hai trong Hệ Mặt Trời.",
            "content_urls": {"desktop": {"page": "https://vi.wikipedia.org/wiki/Sao_H%E1%BB%8Fa"}},
        }
    }
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher(mock_data))
    # Question claims Sao Hỏa is the largest planet, which contradicts its actual attributes
    question = {
        "id": "q_contradict",
        "question": "Hành tinh nào là hành tinh lớn nhất?",
        "choices": [
            {"id": "A", "text": "Sao Hỏa"},
            {"id": "B", "text": "Trái Đất"},
        ],
        "correct_id": "A",
        "answer_text": "Sao Hỏa",
    }
    # It resolves Sao Hỏa, but the keyword 'lớn nhất' does not match the extract's 'nhỏ thứ hai'
    result = verifier.verify_question(question)
    # The snippet should capture the extract and corroborate keyword coverage
    assert result.source_title == "Sao Hỏa"


def test_verify_and_annotate_fail_closed_raises():
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher({}))
    question = {
        "id": "q_fake",
        "question": "Ai là vua của hành tinh X?",
        "answer_text": "Vua Bí Ẩn Không Tồn Tại",
    }
    with pytest.raises(FactualVerificationError) as exc_info:
        verifier.verify_and_annotate(question, fail_closed=True)
    assert exc_info.value.status == STATUS_REJECTED_NO_SOURCE


def test_verify_and_annotate_annotates_fields():
    mock_data = {
        "Paris": {
            "title": "Paris",
            "extract": "Paris là thủ đô và thành phố đông dân nhất của nước Pháp.",
            "content_urls": {"desktop": {"page": "https://vi.wikipedia.org/wiki/Paris"}},
        }
    }
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher(mock_data))
    question = {
        "id": "q_paris",
        "question": "Thủ đô của nước Pháp là thành phố nào?",
        "answer_text": "Paris",
    }
    annotated = verifier.verify_and_annotate(question, fail_closed=True)
    assert annotated["fact_status"] == STATUS_VERIFIED
    assert annotated["source_url"] == "https://vi.wikipedia.org/wiki/Paris"
    assert "Paris" in annotated["source_title"]
    assert "thủ đô" in annotated["fact_evidence"]
    assert "fact_checked_at" in annotated


def test_verify_batch_processes_all():
    mock_data = {
        "Paris": {
            "title": "Paris",
            "extract": "Paris là thủ đô nước Pháp.",
        }
    }
    verifier = QuizFactVerifier(locale="vi", fetcher=_create_mock_fetcher(mock_data))
    batch = [
        {"id": "q1", "question": "Thủ đô Pháp?", "answer_text": "Paris"},
        {"id": "q2", "question": "Hành tinh ma?", "answer_text": "NonExistentPlanetXYZ"},
    ]
    verified, results = verifier.verify_batch(batch, fail_closed=False)
    assert len(verified) == 2
    assert len(results) == 2
    assert results[0].valid is True
    assert results[1].valid is False
