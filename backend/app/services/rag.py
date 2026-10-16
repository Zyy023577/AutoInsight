"""证据约束 RAG 问答编排与安全回答。"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from backend.app.schemas.nlp import NlpAnalysis
from backend.app.schemas.rag import (
    LLMAnswerPayload,
    RagAnswerRequest,
    RagAnswerResponse,
    RagMode,
)
from backend.app.services.llm import LLMUnavailableError
from backend.app.services.retrieval import RetrievalResult, StructuredRetriever


load_dotenv()


class RagOutputValidationError(RuntimeError):
    """模型输出不是合法的证据约束格式。"""


class LLMGroundedAnswerer:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def answer(self, question: str, analysis: NlpAnalysis, retrieval: RetrievalResult) -> tuple[str, list[str], str]:
        if not self.available:
            raise LLMUnavailableError(
                "未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，当前只能使用 demo_grounded"
            )
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=10.0,
                max_retries=2,
            )

        context = self._build_context(retrieval)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=700,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是汽车领域证据约束问答助手。只能使用 CONTEXT 中的事实回答；"
                        "不得补充未出现的价格、续航、配置或评价。证据不足时必须明确说无法验证。"
                        "只返回 JSON：{answer:string,citations:string[],insufficient_evidence:boolean}。"
                        "citations 只能填写 CONTEXT 中的证据编号。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"QUESTION: {question}\nINTENT: {analysis.intent.value}\nCONTEXT:\n{context}",
                },
            ],
        )
        raw_output = response.choices[0].message.content or ""
        try:
            payload = LLMAnswerPayload.model_validate(json.loads(raw_output))
        except Exception as error:
            raise RagOutputValidationError("LLM 输出无法通过 JSON/Pydantic 校验") from error

        allowed = {item.evidence_id for item in retrieval.evidence}
        if any(citation not in allowed for citation in payload.citations):
            raise RagOutputValidationError("LLM 引用了不存在的证据编号")
        if not payload.insufficient_evidence and not payload.citations:
            raise RagOutputValidationError("LLM 在非拒答回答中没有提供证据编号")
        return payload.answer, payload.citations, raw_output

    @staticmethod
    def _build_context(retrieval: RetrievalResult) -> str:
        return "\n".join(
            f"[{item.evidence_id}] {item.statement} | source={item.provenance.source_name} "
            f"| collected_at={item.provenance.collected_at} | data_status={item.provenance.data_status}"
            for item in retrieval.evidence
        )


class RagService:
    def __init__(self, pipeline, retriever: StructuredRetriever, answerer: LLMGroundedAnswerer | None = None):
        self.pipeline = pipeline
        self.retriever = retriever
        self.answerer = answerer or LLMGroundedAnswerer()

    def answer(self, request: RagAnswerRequest) -> RagAnswerResponse:
        analysis = self.pipeline.analyze(request.question)
        retrieval = self.retriever.retrieve(analysis)
        evidence = self._number_evidence(retrieval.evidence)
        retrieval = RetrievalResult(evidence, retrieval.strict_match_count, retrieval.reason)

        if not evidence:
            return self._refusal(request, analysis, retrieval)
        if request.mode == RagMode.LLM_GROUNDED:
            answer, citations, raw_output = self.answerer.answer(request.question, analysis, retrieval)
            return RagAnswerResponse(
                question=request.question,
                analysis=analysis,
                evidence=evidence,
                answer=answer,
                citations=citations,
                mode=request.mode,
                grounded=True,
                raw_output=raw_output,
            )
        return self._demo_answer(request, analysis, retrieval)

    @staticmethod
    def _number_evidence(evidence):
        return [item.model_copy(update={"evidence_id": f"E{index}"}) for index, item in enumerate(evidence, 1)]

    def _refusal(self, request: RagAnswerRequest, analysis: NlpAnalysis, retrieval: RetrievalResult) -> RagAnswerResponse:
        reason = retrieval.reason or "当前结构化知识库没有足够证据"
        return RagAnswerResponse(
            question=request.question,
            analysis=analysis,
            answer=f"当前知识库无法验证这个问题。{reason}。请补充明确车型，或接入经过授权的数据源。",
            citations=[],
            mode=request.mode,
            grounded=False,
            refusal_reason=reason,
            parser_status="no_evidence",
        )

    @staticmethod
    def _demo_answer(request: RagAnswerRequest, analysis: NlpAnalysis, retrieval: RetrievalResult) -> RagAnswerResponse:
        citations = [item.evidence_id for item in retrieval.evidence]
        source_names = sorted({item.provenance.source_name for item in retrieval.evidence})
        if analysis.intent.value == "购车推荐":
            if retrieval.strict_match_count:
                answer = (
                    f"基于当前 Demo 知识库，找到 {retrieval.strict_match_count} 个满足已声明硬约束的候选。"
                    f"结果和原因请以证据编号 {', '.join(citations)} 为准。来源：{'、'.join(source_names)}。"
                )
            else:
                answer = (
                    "当前 Demo 知识库没有找到同时满足全部硬约束的车型；返回的证据仅用于说明接近候选，"
                    f"不能视为满足条件。来源：{'、'.join(source_names)}。"
                )
        else:
            answer = (
                f"已从当前 Demo 知识库检索到 {len(retrieval.evidence)} 条相关证据。"
                f"回答仅依据证据编号 {', '.join(citations)}，来源：{'、'.join(source_names)}。"
            )
        return RagAnswerResponse(
            question=request.question,
            analysis=analysis,
            evidence=retrieval.evidence,
            answer=answer,
            citations=citations,
            mode=request.mode,
            grounded=True,
        )
