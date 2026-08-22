"""Frozen metadata rules for the share-repurchase event count probe."""

from __future__ import annotations

import re


INITIAL_PHRASES = (
    "回购股份方案", "回购公司股份方案", "股份回购方案",
    "回购股份预案", "回购公司股份预案", "股份回购预案",
    "回购股份提议", "提议回购股份", "提议公司回购股份", "关于提议回购公司股份",
    "董事会审议通过回购股份", "董事会审议通过回购公司股份",
)
EXCLUDED_STATES = {
    "progress": ("进展", "首次回购", "首次实施", "实施回购", "回购报告书", "回购股份报告书"),
    "completion": ("回购结果", "实施结果", "完成", "期限届满", "届满"),
    "cancel_change": ("终止", "停止", "取消", "撤回", "变更", "调整", "注销", "出售"),
    "correction": ("更正", "补充", "修订", "更新", "提示性", "延期", "延长"),
    "later_mechanics": ("股东大会决议", "债权人通知", "通知债权人", "回购专用证券账户", "回购专户"),
}
OTHER_CONTEXT = ("员工持股计划", "股权激励", "可转换公司债券", "可转债", "基金份额")


def normalize_title(title: str) -> str:
    value = re.sub(r"<[^>]+>", "", title)
    value = re.sub(r"[\s\u3000\W_]+", "", value, flags=re.UNICODE)
    return re.sub(r"^(?:[\w\u4e00-\u9fff]{0,20})?公司关于", "关于", value)


def classify_title(title: str) -> str:
    """Classify one announcement title without document or market data."""
    value = normalize_title(title)
    if "回购" not in value or not ("股份" in value or "股票" in value):
        return "other"
    if any(phrase in value for phrase in OTHER_CONTEXT):
        return "other"
    for state, phrases in EXCLUDED_STATES.items():
        if any(phrase in value for phrase in phrases):
            return state
    board_resolution = "董事会决议公告" in value and any(
        phrase in value for phrase in ("回购股份方案", "回购公司股份方案")
    )
    return "initial" if board_resolution or any(phrase in value for phrase in INITIAL_PHRASES) else "other"
