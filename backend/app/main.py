"""AutoInsight Phase 4 FastAPI 应用入口。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.database import connect, database_path, initialize_database
from backend.app.schemas.car import CarListResponse, CarRecord, HealthResponse
from backend.app.schemas.evaluation import (
    EvaluationReportResponse,
    LLMConfigRequest,
    LLMConfigResponse,
    PromptExperimentRequest,
    PromptExperimentResponse,
)
from backend.app.schemas.knowledge import ComparisonResponse, KnowledgeGraphResponse
from backend.app.schemas.nlp import AnalyzeRequest, AnalysisStrategy, NlpAnalysis
from backend.app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from backend.app.schemas.rag import RagAnswerRequest, RagAnswerResponse
from backend.app.services.car_catalog import CarCatalog
from backend.app.services.llm import LLMStructuredAnalyzer, LLMUnavailableError
from backend.app.services.knowledge import KnowledgeGraphService
from backend.app.services.nlp_pipeline import RuleNlpPipeline
from backend.app.services.recommendation import RecommendationService
from backend.app.services.rag import RagOutputValidationError, RagService
from backend.app.services.retrieval import StructuredRetriever
from backend.app.evaluation.runner import EvaluationRunner


def create_app(db_path=None) -> FastAPI:
    selected_db_path = db_path or database_path()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_database(selected_db_path)
        yield

    app = FastAPI(
        title="AutoInsight API",
        description="汽车垂类智能问答与大模型策略优化系统的 Phase 4 RAG API",
        version="0.4.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    catalog = CarCatalog(lambda: connect(selected_db_path))
    rule_pipeline = RuleNlpPipeline()
    llm_analyzer = LLMStructuredAnalyzer()
    recommendation_service = RecommendationService()
    rag_service = RagService(
        rule_pipeline,
        StructuredRetriever(catalog, recommendation_service),
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="autoinsight-backend",
            database="ready",
            data_mode="demo",
            car_count=catalog.count(),
        )

    @app.get("/api/cars", response_model=CarListResponse, tags=["cars"])
    def list_cars(
        price_max: int | None = Query(default=None, ge=0, description="预算上限，单位：元"),
        energy_type: str | None = Query(default=None, description="能源类型"),
        body_type: str | None = Query(default=None, description="车身类型"),
        range_min_km: int | None = Query(default=None, ge=0, description="最低续航，单位：公里"),
        usage_scenario: str | None = Query(default=None, description="使用场景"),
    ) -> CarListResponse:
        cars = catalog.list_cars(
            price_max=price_max,
            energy_type=energy_type,
            body_type=body_type,
            range_min_km=range_min_km,
            usage_scenario=usage_scenario,
        )
        return CarListResponse(total=len(cars), data_mode="demo", cars=cars)

    @app.get("/api/cars/{car_id}", response_model=CarRecord, tags=["cars"])
    def get_car(car_id: str) -> CarRecord:
        car = catalog.get(car_id)
        if car is None:
            raise HTTPException(status_code=404, detail=f"未找到车型：{car_id}")
        return car

    @app.post("/api/nlp/analyze", response_model=NlpAnalysis, tags=["nlp"])
    def analyze_nlp(request: AnalyzeRequest) -> NlpAnalysis:
        if request.strategy == AnalysisStrategy.RULE_BASELINE:
            return rule_pipeline.analyze(request.text)
        try:
            return llm_analyzer.analyze(request.text)
        except LLMUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/api/knowledge/graph", response_model=KnowledgeGraphResponse, tags=["knowledge"])
    def knowledge_graph(car_id: str | None = Query(default=None)) -> KnowledgeGraphResponse:
        graph = KnowledgeGraphService(catalog.list_cars())
        try:
            return graph.to_response(car_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"未找到车型：{error.args[0]}") from error

    @app.get("/api/knowledge/compare", response_model=ComparisonResponse, tags=["knowledge"])
    def compare_cars(
        car_ids: list[str] = Query(min_length=2, max_length=4),
    ) -> ComparisonResponse:
        graph = KnowledgeGraphService(catalog.list_cars())
        try:
            return graph.compare(car_ids)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"未找到车型：{error.args[0]}") from error

    @app.post(
        "/api/recommendations",
        response_model=RecommendationResponse,
        tags=["recommendations"],
    )
    def recommendations(request: RecommendationRequest) -> RecommendationResponse:
        return recommendation_service.recommend(catalog.list_cars(), request)

    @app.post("/api/qa/answer", response_model=RagAnswerResponse, tags=["qa"])
    def answer_question(request: RagAnswerRequest) -> RagAnswerResponse:
        try:
            return rag_service.answer(request)
        except LLMUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RagOutputValidationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @app.get(
        "/api/evaluation/report",
        response_model=EvaluationReportResponse,
        tags=["evaluation"],
    )
    def evaluation_report() -> EvaluationReportResponse:
        report_path = Path(__file__).resolve().parents[2] / "reports" / "generated" / "evaluation_results.json"
        if not report_path.exists():
            raise HTTPException(status_code=404, detail="尚未生成评测报告，请先运行 python scripts\\run_evaluation.py")
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return EvaluationReportResponse(
            dataset_type=payload.get("dataset_type", "unknown"),
            rule_baseline=payload["rule_baseline"],
            prompt_strategies=payload.get("strategies", []),
            report_path=str(report_path),
        )

    @app.get("/api/evaluation/errors", response_model=list[dict], tags=["evaluation"])
    def evaluation_errors() -> list[dict]:
        error_path = Path(__file__).resolve().parents[2] / "reports" / "generated" / "error_cases.json"
        if not error_path.exists():
            raise HTTPException(status_code=404, detail="尚未生成错误案例，请先运行评测脚本")
        return json.loads(error_path.read_text(encoding="utf-8"))

    @app.post(
        "/api/evaluation/prompt",
        response_model=PromptExperimentResponse,
        tags=["evaluation"],
    )
    def prompt_experiment(request: PromptExperimentRequest) -> PromptExperimentResponse:
        dataset_path = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "intent_entity_eval.json"
        try:
            record = EvaluationRunner(dataset_path).run_prompt_strategy_sample(
                request.strategy_id,
                request.text,
            )
        except LLMUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return PromptExperimentResponse(
            strategy_id=record.strategy_id,
            prompt_version=record.prompt_version,
            text=record.text,
            intent=record.predicted_intent or "",
            entities=record.predicted_entities,
            raw_output=record.raw_output,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            latency_ms=record.latency_ms,
        )

    @app.get("/api/settings/llm", response_model=LLMConfigResponse, tags=["settings"])
    def get_llm_settings() -> LLMConfigResponse:
        return LLMConfigResponse(
            configured=llm_analyzer.available,
            base_url=llm_analyzer.base_url,
            model=llm_analyzer.model,
            persistence=llm_analyzer.persistence,
        )

    @app.post("/api/settings/llm", response_model=LLMConfigResponse, tags=["settings"])
    def configure_llm(request: Request, config: LLMConfigRequest) -> LLMConfigResponse:
        client_host = request.client.host if request.client else "127.0.0.1"
        if client_host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="模型配置接口只允许本机访问")
        llm_analyzer.configure_runtime(
            config.api_key,
            config.base_url,
            config.model,
            persist=config.persist,
        )
        return LLMConfigResponse(
            configured=llm_analyzer.available,
            base_url=llm_analyzer.base_url,
            model=llm_analyzer.model,
            persistence=llm_analyzer.persistence,
        )

    return app


app = create_app()
