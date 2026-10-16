"""汽车领域规则意图分类 Baseline。"""

from __future__ import annotations

import re

from backend.app.schemas.nlp import IntentLabel


INTENT_DESCRIPTIONS: dict[IntentLabel, str] = {
    IntentLabel.PURCHASE_RECOMMENDATION: "根据预算、偏好或使用场景寻找车型",
    IntentLabel.MODEL_COMPARISON: "比较两个或多个车型的差异",
    IntentLabel.PARAMETER_QUERY: "查询续航、尺寸、动力或配置等参数",
    IntentLabel.PRICE_QUERY: "查询指导价、售价、落地价或购车预算信息",
    IntentLabel.USER_REVIEW: "询问口碑、优缺点、质量或用户评价",
    IntentLabel.USAGE_KNOWLEDGE: "询问保养、充电、保险等用车知识",
    IntentLabel.OTHER: "无法归入汽车消费核心意图的问题",
}


class RuleIntentClassifier:
    """可解释的关键词规则分类器，不输出伪造概率。"""

    # 顺序表示冲突时的确定性优先级：比较通常比单项查询更明确。
    _rules: tuple[tuple[IntentLabel, tuple[str, ...]], ...] = (
        (
            IntentLabel.MODEL_COMPARISON,
            ("对比", "比较", "哪个好", "怎么选", "区别", "相比", "pk", "vs"),
        ),
        (
            IntentLabel.PURCHASE_RECOMMENDATION,
            ("推荐", "买车", "选车", "有什么车", "适合", "想买", "购车"),
        ),
        (
            IntentLabel.PRICE_QUERY,
            ("价格", "售价", "指导价", "落地", "多少钱", "贵不贵"),
        ),
        (
            IntentLabel.USER_REVIEW,
            ("口碑", "评价", "缺点", "优点", "质量", "小毛病", "后悔"),
        ),
        (
            IntentLabel.USAGE_KNOWLEDGE,
            ("保养", "保险", "充电桩", "充电费用", "首保", "用车", "购置税"),
        ),
        (
            IntentLabel.PARAMETER_QUERY,
            ("续航", "轴距", "尺寸", "动力", "配置", "参数", "百公里", "快充"),
        ),
    )

    def classify(self, text: str) -> tuple[IntentLabel, list[str]]:
        normalized = re.sub(r"\s+", "", text.lower())
        for label, keywords in self._rules:
            hits = [keyword for keyword in keywords if keyword in normalized]
            if hits:
                return label, hits
        return IntentLabel.OTHER, []

    def explain(self, text: str) -> str:
        label, hits = self.classify(text)
        if not hits:
            return f"未命中规则，归类为{label.value}"
        return f"命中{label.value}规则：" + "、".join(hits)
