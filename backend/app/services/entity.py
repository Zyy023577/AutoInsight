"""汽车实体与约束的规则抽取器。"""

from __future__ import annotations

import re
import unicodedata

from backend.app.schemas.nlp import ConstraintRecord, ExtractedEntities, IntentLabel


BRAND_ALIASES: tuple[tuple[str, str], ...] = (
    ("AutoInsight Demo", "AutoInsight Demo"),
    ("比亚迪", "比亚迪"),
    ("特斯拉", "特斯拉"),
    ("小米", "小米"),
    ("理想", "理想"),
    ("蔚来", "蔚来"),
    ("小鹏", "小鹏"),
    ("问界", "问界"),
    ("极氪", "极氪"),
)

MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("model y", "特斯拉 Model Y"),
    ("modely", "特斯拉 Model Y"),
    ("宋plus", "比亚迪 宋PLUS"),
    ("宋 plus", "比亚迪 宋PLUS"),
    ("su7", "小米 SU7"),
    ("理想l7", "理想 L7"),
    ("蔚来es6", "蔚来 ES6"),
)

ENERGY_ALIASES: tuple[tuple[str, str], ...] = (
    ("插电混动", "插电混动"),
    ("插混", "插电混动"),
    ("纯电动", "纯电"),
    ("纯电", "纯电"),
    ("电车", "纯电"),
    ("混合动力", "混合动力"),
    ("油混", "混合动力"),
    ("混动", "混合动力"),
    ("燃油", "燃油"),
    ("油车", "燃油"),
)

BODY_ALIASES: tuple[tuple[str, str], ...] = (
    ("SUV", "SUV"),
    ("suv", "SUV"),
    ("MPV", "MPV"),
    ("mpv", "MPV"),
    ("轿车", "轿车"),
    ("三厢车", "轿车"),
    ("越野车", "越野车"),
)

SCENARIO_ALIASES: tuple[tuple[str, str], ...] = (
    ("家庭使用", "家庭使用"),
    ("家用", "家庭使用"),
    ("通勤", "城市通勤"),
    ("城市代步", "城市通勤"),
    ("长途", "长途出行"),
    ("自驾", "长途出行"),
    ("户外", "户外出行"),
    ("多人出行", "多人出行"),
)

FOCUS_ALIASES: tuple[tuple[str, str], ...] = (
    ("空间", "空间"),
    ("舒适", "舒适性"),
    ("智能", "智能化"),
    ("能耗", "能耗"),
    ("省电", "能耗"),
    ("安全", "安全性"),
    ("保值", "保值率"),
    ("性价比", "性价比"),
    ("续航", "续航"),
    ("动力", "动力"),
)

CONFIGURATION_ALIASES: tuple[tuple[str, str], ...] = (
    ("四驱", "四驱"),
    ("激光雷达", "激光雷达"),
    ("辅助驾驶", "辅助驾驶"),
    ("座椅加热", "座椅加热"),
    ("快充", "快充"),
    ("智能座舱", "智能座舱"),
    ("后排空间", "后排空间"),
)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 8) : start]
    return bool(re.search(r"不考虑|不要|不想要|排除|拒绝|不选", prefix))


class RuleEntityExtractor:
    """从自然语言中抽取可解释的结构化实体和约束。"""

    def extract(self, text: str, intent: IntentLabel = IntentLabel.OTHER) -> ExtractedEntities:
        normalized = _normalized(text)
        result = ExtractedEntities()

        result.brands = self._find_aliases(normalized, BRAND_ALIASES)
        result.models = self._find_aliases(normalized, MODEL_ALIASES)
        self._extract_budget(normalized, result)
        self._extract_energy(normalized, result, intent)
        self._extract_body(normalized, result, intent)
        self._extract_range(normalized, result)
        result.usage_scenarios = self._find_aliases(normalized, SCENARIO_ALIASES)
        result.focus_attributes = self._find_aliases(normalized, FOCUS_ALIASES)
        result.configurations = self._find_aliases(normalized, CONFIGURATION_ALIASES)

        if "宋" in normalized and "宋plus" not in normalized and "宋 plus" not in normalized:
            result.ambiguous_mentions.append("宋（缺少完整车型名称）")

        for scenario in result.usage_scenarios:
            result.soft_preferences.append(
                ConstraintRecord(
                    field="usage_scenario",
                    operator="contains",
                    value=scenario,
                    source_text=scenario,
                )
            )
        for attribute in result.focus_attributes:
            result.soft_preferences.append(
                ConstraintRecord(
                    field="focus_attribute",
                    operator="contains",
                    value=attribute,
                    source_text=attribute,
                )
            )

        return result

    @staticmethod
    def _find_aliases(text: str, aliases: tuple[tuple[str, str], ...]) -> list[str]:
        found: list[str] = []
        for alias, canonical in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
            if alias.lower() in text and canonical not in found:
                found.append(canonical)
        return found

    @staticmethod
    def _extract_budget(text: str, result: ExtractedEntities) -> None:
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:万|万元)\s*(?:到|至|~|-)\s*"
            r"(\d+(?:\.\d+)?)\s*(?:万|万元)",
            text,
        )
        if range_match:
            minimum = int(float(range_match.group(1)) * 10000)
            maximum = int(float(range_match.group(2)) * 10000)
            result.budget_min, result.budget_max = minimum, maximum
            result.hard_constraints.append(
                ConstraintRecord(
                    field="budget",
                    operator="between",
                    value=f"{minimum}-{maximum}",
                    source_text=range_match.group(0),
                )
            )
            return

        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(万|万元)", text):
            value = int(float(match.group(1)) * 10000)
            suffix = text[match.end() : match.end() + 8]
            source = match.group(0) + suffix[:4]
            if re.search(r"以内|以下|不超过|最多|上限", suffix):
                result.budget_max = value
                operator = "lte"
                target = result.hard_constraints
            elif re.search(r"以上|不少于|最低|起步", suffix):
                result.budget_min = value
                operator = "gte"
                target = result.hard_constraints
            else:
                result.budget_max = value
                operator = "lte"
                target = result.soft_preferences
            target.append(
                ConstraintRecord(field="budget", operator=operator, value=value, source_text=source)
            )

    def _extract_energy(
        self, text: str, result: ExtractedEntities, intent: IntentLabel
    ) -> None:
        for alias, canonical in sorted(ENERGY_ALIASES, key=lambda item: len(item[0]), reverse=True):
            start = text.find(alias.lower())
            if start < 0:
                continue
            if _is_negated(text, start):
                result.negative_constraints.append(
                    ConstraintRecord(
                        field="energy_type",
                        operator="not",
                        value=canonical,
                        source_text=alias,
                    )
                )
            else:
                result.energy_type = canonical
                target = result.hard_constraints if intent == IntentLabel.PURCHASE_RECOMMENDATION else result.soft_preferences
                target.append(
                    ConstraintRecord(field="energy_type", operator="eq", value=canonical, source_text=alias)
                )
            return

    def _extract_body(self, text: str, result: ExtractedEntities, intent: IntentLabel) -> None:
        for alias, canonical in sorted(BODY_ALIASES, key=lambda item: len(item[0]), reverse=True):
            start = text.find(alias.lower())
            if start < 0:
                continue
            if _is_negated(text, start):
                result.negative_constraints.append(
                    ConstraintRecord(
                        field="body_type",
                        operator="not",
                        value=canonical,
                        source_text=alias,
                    )
                )
            else:
                result.body_type = canonical
                target = result.hard_constraints if intent == IntentLabel.PURCHASE_RECOMMENDATION else result.soft_preferences
                target.append(
                    ConstraintRecord(field="body_type", operator="eq", value=canonical, source_text=alias)
                )
            return

    @staticmethod
    def _extract_range(text: str, result: ExtractedEntities) -> None:
        match = re.search(
            r"(?:续航|里程)[^。；，,]{0,8}?(\d{3,4})\s*(?:公里|km|千米)?\s*"
            r"(以上|至少|不低于|起步)?",
            text,
        )
        if not match:
            return
        value = int(match.group(1))
        result.range_min_km = value
        operator = "gte" if match.group(2) else "eq"
        result.hard_constraints.append(
            ConstraintRecord(
                field="range_km",
                operator=operator,
                value=value,
                source_text=match.group(0),
            )
        )
