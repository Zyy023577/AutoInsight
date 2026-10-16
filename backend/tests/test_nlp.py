from pathlib import Path

from backend.app.schemas.nlp import ExtractedEntities, IntentLabel, normalize_llm_payload
from backend.app.services import llm as llm_module
from backend.app.services.entity import RuleEntityExtractor
from backend.app.services.intent import RuleIntentClassifier
from backend.app.services.llm import LLMStructuredAnalyzer
from backend.app.services.nlp_pipeline import RuleNlpPipeline


def test_intent_rules_cover_core_categories():
    classifier = RuleIntentClassifier()
    cases = {
        "20万以内有什么新能源SUV推荐？": IntentLabel.PURCHASE_RECOMMENDATION,
        "比亚迪宋PLUS和特斯拉Model Y哪个好？": IntentLabel.MODEL_COMPARISON,
        "小米SU7的续航怎么样？": IntentLabel.PARAMETER_QUERY,
        "Model Y现在多少钱？": IntentLabel.PRICE_QUERY,
        "这款车有什么常见缺点？": IntentLabel.USER_REVIEW,
        "新能源车日常怎么保养？": IntentLabel.USAGE_KNOWLEDGE,
        "今天天气怎么样？": IntentLabel.OTHER,
    }
    for text, expected in cases.items():
        label, hits = classifier.classify(text)
        assert label == expected
        if expected == IntentLabel.OTHER:
            assert hits == []
        else:
            assert hits


def test_entity_extraction_normalizes_constraints_and_aliases():
    text = "我想买一辆20万以内、续航500公里以上、适合家用的纯电SUV。"
    result = RuleNlpPipeline().analyze(text)

    assert result.intent == IntentLabel.PURCHASE_RECOMMENDATION
    assert result.entities.budget_max == 200000
    assert result.entities.range_min_km == 500
    assert result.entities.energy_type == "纯电"
    assert result.entities.body_type == "SUV"
    assert result.entities.usage_scenarios == ["家庭使用"]
    assert {item.field for item in result.entities.hard_constraints} == {
        "budget",
        "range_km",
        "energy_type",
        "body_type",
    }


def test_entity_extraction_supports_aliases_negation_and_ambiguity():
    extractor = RuleEntityExtractor()
    result = extractor.extract("不考虑纯电，想看看宋，预算15万左右")

    assert result.models == []
    assert result.budget_max == 150000
    assert any(item.value == "纯电" for item in result.negative_constraints)
    assert result.ambiguous_mentions == ["宋（缺少完整车型名称）"]
    assert any(item.field == "budget" for item in result.soft_preferences)

    aliases = extractor.extract("比亚迪宋PLUS和特斯拉Model Y怎么选？")
    assert aliases.models == ["特斯拉 Model Y", "比亚迪 宋PLUS"]


def test_entity_schema_keeps_missing_fields_explicit():
    result = RuleEntityExtractor().extract("推荐一台车")

    assert result.budget_max is None
    assert result.range_min_km is None
    assert result.hard_constraints == []


def test_entity_schema_normalizes_structured_model_mentions():
    result = ExtractedEntities.model_validate(
        {
            "models": [
                {"brand": "小米", "model": "SU7", "trim": None},
                {"brand": "特斯拉", "model": "Model Y", "trim": None},
            ]
        }
    )

    assert result.models == ["小米 SU7", "特斯拉 Model Y"]


def test_llm_adapter_validates_structured_json_without_network(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    analyzer = LLMStructuredAnalyzer()

    class FakeMessage:
        content = '{"intent":"价格查询","entities":{"models":["小米 SU7"]}}'

    class FakeResponse:
        choices = [type("Choice", (), {"message": FakeMessage()})()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return FakeResponse()

    analyzer._client = FakeClient()
    result = analyzer.analyze("小米SU7多少钱？")

    assert result.intent == IntentLabel.PRICE_QUERY
    assert result.entities.models == ["小米 SU7"]
    assert result.strategy.value == "llm_structured"
    assert result.raw_output is not None


def test_llm_adapter_normalizes_structured_model_objects(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    analyzer = LLMStructuredAnalyzer()

    class FakeMessage:
        content = (
            '{"intent":"comparison","entities":'
            '[{"brand":"小米","model":"SU7","trim":null},'
            '{"brand":"特斯拉","model":"Model Y","trim":null}]}'
        )

    class FakeResponse:
        choices = [type("Choice", (), {"message": FakeMessage()})()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return FakeResponse()

    analyzer._client = FakeClient()
    result = analyzer.analyze("小米SU7和特斯拉Model Y哪个好？")

    assert result.intent == IntentLabel.MODEL_COMPARISON
    assert result.entities.models == ["小米 SU7", "特斯拉 Model Y"]


def test_llm_runtime_config_can_persist_to_local_env(monkeypatch):
    env_path = Path(__file__).parent / ".test-data" / "persist-test.env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.unlink(missing_ok=True)
    monkeypatch.setattr(llm_module, "LOCAL_ENV_PATH", env_path)
    analyzer = llm_module.LLMStructuredAnalyzer()

    analyzer.configure_runtime(
        "test-only-not-a-real-key",
        "https://api.deepseek.com",
        "deepseek-chat",
        persist=True,
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY='test-only-not-a-real-key'" in saved
    assert analyzer.persistence == "local_env"
    env_path.unlink(missing_ok=True)


def test_llm_payload_normalizes_structured_constraint_objects():
    payload = normalize_llm_payload(
        {
            "intent": "comparison",
            "entities": {
                "hard_constraints": {"models": ["小米SU7", "特斯拉Model Y"]},
                "soft_preferences": {"comparison_aspects": ["续航"]},
                "negative_constraints": {"exclude_models": []},
            },
        }
    )
    entities = ExtractedEntities.model_validate(payload["entities"])

    assert entities.models == ["小米SU7", "特斯拉Model Y"]
    assert entities.focus_attributes == ["续航"]
    assert entities.hard_constraints[0].field == "models"
    assert entities.negative_constraints == []
