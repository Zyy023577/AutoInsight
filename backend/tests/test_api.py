from __future__ import annotations

import asyncio

import httpx


def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send_request())


def test_health_reports_demo_database(test_app):
    response = request(test_app, "GET", "/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ready"
    assert body["data_mode"] == "demo"
    assert body["car_count"] == 6


def test_list_cars_and_filter_by_constraints(test_app):
    all_cars = request(test_app, "GET", "/api/cars")
    filtered = request(
        test_app,
        "GET",
        "/api/cars",
        params={
            "price_max": 200000,
            "energy_type": "纯电",
            "body_type": "SUV",
            "range_min_km": 500,
            "usage_scenario": "家庭",
        },
    )

    assert all_cars.status_code == 200
    assert all_cars.json()["total"] == 6
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["cars"][0]["id"] == "demo-ev-suv-a"


def test_get_car_and_missing_car(test_app):
    found = request(test_app, "GET", "/api/cars/demo-ev-suv-a")
    missing = request(test_app, "GET", "/api/cars/not-exists")

    assert found.status_code == 200
    assert found.json()["data_status"] == "demo"
    assert found.json()["source_name"] == "AutoInsight Demo synthetic dataset"
    assert missing.status_code == 404


def test_nlp_rule_endpoint_returns_structured_analysis(test_app):
    response = request(
        test_app,
        "POST",
        "/api/nlp/analyze",
        json={"text": "20万以内有什么纯电SUV推荐？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "rule_baseline"
    assert body["intent"] == "购车推荐"
    assert body["entities"]["budget_max"] == 200000
    assert body["entities"]["energy_type"] == "纯电"
    assert body["entities"]["body_type"] == "SUV"


def test_nlp_endpoint_rejects_blank_question(test_app):
    response = request(
        test_app,
        "POST",
        "/api/nlp/analyze",
        json={"text": "   "},
    )

    assert response.status_code == 422


def test_rag_demo_endpoint_returns_evidence(test_app):
    response = request(
        test_app,
        "POST",
        "/api/qa/answer",
        json={"question": "20万以内有什么纯电SUV推荐？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo_grounded"
    assert body["grounded"] is True
    assert body["evidence"]
    assert body["citations"] == [item["evidence_id"] for item in body["evidence"]]


def test_rag_demo_endpoint_refuses_unknown_model(test_app):
    response = request(
        test_app,
        "POST",
        "/api/qa/answer",
        json={"question": "火星汽车X的2028年真实售价是多少？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["parser_status"] == "no_evidence"


def test_evaluation_report_endpoint_exposes_generated_results(test_app):
    response = request(test_app, "GET", "/api/evaluation/report")

    assert response.status_code == 200
    body = response.json()
    assert body["rule_baseline"]["sample_count"] == 100
    assert {item["strategy_id"] for item in body["prompt_strategies"]} == {"A", "B", "C"}


def test_evaluation_errors_endpoint_exposes_error_cases(test_app):
    response = request(test_app, "GET", "/api/evaluation/errors")

    assert response.status_code == 200
    assert len(response.json()) == 14


def test_prompt_experiment_requires_api_key(test_app, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = request(
        test_app,
        "POST",
        "/api/evaluation/prompt",
        json={"strategy_id": "A", "text": "20万以内有什么纯电SUV推荐？"},
    )

    assert response.status_code == 503


def test_llm_settings_endpoint_keeps_key_out_of_response(test_app):
    response = request(
        test_app,
        "POST",
        "/api/settings/llm",
        json={
            "api_key": "test-only-not-a-real-key",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "persist": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert "api_key" not in body
    assert body["persistence"] == "process_memory_only"
