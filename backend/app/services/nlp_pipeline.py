"""规则 NLP 分析流水线。"""

from __future__ import annotations

from backend.app.schemas.nlp import AnalysisStrategy, NlpAnalysis
from backend.app.services.entity import RuleEntityExtractor
from backend.app.services.intent import RuleIntentClassifier


class RuleNlpPipeline:
    def __init__(self) -> None:
        self.intent_classifier = RuleIntentClassifier()
        self.entity_extractor = RuleEntityExtractor()

    def analyze(self, text: str) -> NlpAnalysis:
        intent, hits = self.intent_classifier.classify(text)
        entities = self.entity_extractor.extract(text, intent)
        return NlpAnalysis(
            text=text,
            intent=intent,
            intent_evidence=hits,
            entities=entities,
            strategy=AnalysisStrategy.RULE_BASELINE,
        )
