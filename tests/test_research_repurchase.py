from ashare_edge_scout.research_repurchase import classify_title, normalize_title


def test_normalize_title_removes_markup_spacing_and_issuer_prefix() -> None:
    assert normalize_title("甲公司关于 <em>回购</em> 股份方案的公告") == "关于回购股份方案的公告"


def test_initial_proposal_and_board_resolution_titles_are_accepted() -> None:
    assert classify_title("关于回购公司股份方案的公告") == "initial"
    assert classify_title("实际控制人提议公司回购股份的公告") == "initial"
    assert classify_title("第十届董事会决议公告：审议回购股份方案") == "initial"


def test_later_states_override_proposal_words() -> None:
    assert classify_title("关于回购股份方案实施进展的公告") == "progress"
    assert classify_title("关于回购股份方案实施完成暨回购结果的公告") == "completion"
    assert classify_title("关于终止回购股份方案的公告") == "cancel_change"
    assert classify_title("关于回购股份方案的更正公告") == "correction"
    assert classify_title("股东大会决议公告：回购股份方案") == "later_mechanics"


def test_non_issuer_share_context_is_other() -> None:
    assert classify_title("关于回购注销股权激励限制性股票的公告") == "other"
    assert classify_title("关于基金份额回购安排的公告") == "other"
    assert classify_title("关于回购债券的公告") == "other"
