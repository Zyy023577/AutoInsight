from pathlib import Path

import pytest

from backend.app.schemas.rag import RagAnswerRequest, RagMode
from backend.app.services.car_catalog import CarCatalog
from backend.app.services.llm import LLMUnavailableError
from backend.app.services.rag import LLMGroundedAnswerer, RagService
from backend.app.services.recommendation import RecommendationService
from backend.app.services.retrieval import StructuredRetriever
from backend.app.services.nlp_pipeline import RuleNlpPipeline
from backend.app.core.database import connect


def make_rag_service(answerer=None):
    catalog = CarCatalog(lambda: connect(Path("backend/tests/.test-data/test.db")))
    retriever = StructuredRetriever(catalog, RecommendationService())
    return RagService(RuleNlpPipeline(), retriever, answerer=answerer)


def test_demo_rag_returns_evidence_and_sources(test_app):
    result = make_rag_service().answer(
        RagAnswerRequest(question="20万以内有什么纯电SUV推荐？")
    )

    assert result.mode == RagMode.DEMO_GROUNDED
    assert result.grounded is True
    assert result.evidence
    assert result.citations == [item.evidence_id for item in result.evidence]
    assert "AutoInsight Demo synthetic dataset" in result.answer
    assert all(item.provenance.data_status == "demo" for item in result.evidence)


def test_rag_refuses_when_structured_knowledge_is_insufficient(test_app):
    result = make_rag_service().answer(
        RagAnswerRequest(question="请告诉我火星汽车X的2028年真实售价")
    )

    assert result.grounded is False
    assert result.citations == []
    assert result.parser_status == "no_evidence"
    assert "无法验证" in result.answer


def test_llm_mode_requires_key_and_does_not_fallback_silently(test_app, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMUnavailableError):
        make_rag_service().answer(
            RagAnswerRequest(
                question="家庭纯电 SUV A 的续航是多少？",
                mode=RagMode.LLM_GROUNDED,
            )
        )


def test_fake_llm_answer_must_cite_existing_evidence(test_app, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    answerer = LLMGroundedAnswerer()

    class FakeMessage:
        content = '{"answer":"依据证据回答。","citations":["E1"],"insufficient_evidence":false}'

    class FakeResponse:
        choices = [type("Choice", (), {"message": FakeMessage()})()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return FakeResponse()

    answerer._client = FakeClient()
    result = make_rag_service(answerer).answer(
        RagAnswerRequest(
            question="家庭纯电 SUV A 的续航是多少？",
            mode=RagMode.LLM_GROUNDED,
        )
    )

    assert result.grounded is True
    assert result.citations == ["E1"]
    assert result.raw_output is not None
