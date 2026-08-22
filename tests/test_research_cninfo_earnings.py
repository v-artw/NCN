from ashare_edge_scout.research_cninfo_earnings import link_correction_chains, parse_earnings_text


def test_parses_unambiguous_parent_profit_and_growth_range():
    text = """
    2024年年度业绩预告
    预计归属于上市公司股东的净利润为8,000万元至12,000万元，
    与上年同期相比，同比增长30.00%至50.00%。
    """
    parsed = parse_earnings_text("甲公司2024年年度业绩预告", text)
    assert parsed == {
        "report_type": "forecast", "is_correction": False, "parseable": True,
        "rejection_reason": None, "reporting_period": "2024-年度",
        "parent_net_profit_lower_yuan": 80_000_000.0, "yoy_growth_lower_pct": 30.0,
    }


def test_rejects_multiple_reporting_periods():
    text = "2024年年度及2023年年度归属于母公司所有者的净利润为1亿元至2亿元，同比增长30%至40%。"
    parsed = parse_earnings_text("甲公司2024年年度业绩快报", text)
    assert parsed["rejection_reason"] == "ambiguous_reporting_period"


def test_rejects_conflicting_parent_profit_ranges():
    text = """
    2025年年度归属于母公司所有者的净利润为1亿元至2亿元，同比增长30%至40%。
    归属于母公司所有者的净利润为3亿元至4亿元，同比增长50%至60%。
    """
    parsed = parse_earnings_text("甲公司2025年年度业绩预告", text)
    assert parsed["rejection_reason"] == "ambiguous_parent_profit_lower_bound"


def test_rejects_missing_explicit_yoy_growth():
    text = "2025年年度归属于上市公司股东的净利润为1亿元至2亿元，经营情况改善。"
    parsed = parse_earnings_text("甲公司2025年年度业绩预告", text)
    assert parsed["rejection_reason"] == "ambiguous_yoy_growth_lower_bound"


def test_links_only_unique_earlier_original():
    events = [
        {"announcement_id": "1", "code": "600000", "timestamp_ms": 1,
         "parsed": {"is_correction": False, "reporting_period": "2024-年度", "report_type": "forecast"}},
        {"announcement_id": "2", "code": "600000", "timestamp_ms": 2,
         "parsed": {"is_correction": True, "reporting_period": "2024-年度", "report_type": "forecast"}},
        {"announcement_id": "3", "code": "600000", "timestamp_ms": 3,
         "parsed": {"is_correction": True, "reporting_period": "2025-年度", "report_type": "forecast"}},
    ]
    assert link_correction_chains(events) == [
        {"original_announcement_id": "1", "correction_announcement_id": "2"}
    ]


def test_correction_title_remains_separate_event_type():
    text = "2024年年度归属于上市公司股东的净利润为1亿元至2亿元，同比增长30%至40%。"
    parsed = parse_earnings_text("甲公司2024年年度业绩预告更正公告", text)
    assert parsed["parseable"] is True
    assert parsed["is_correction"] is True
