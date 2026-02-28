from qbot.setops import (
    build_overlap_text,
    collect_candidates,
    is_zheji_candidate,
    is_zheruan_candidate,
    parse_zheji_score,
    parse_zheruan_score,
)


def test_is_zheruan_candidate() -> None:
    assert is_zheruan_candidate("420-张三")
    assert not is_zheruan_candidate("26-计科-420-张三")


def test_is_zheji_candidate() -> None:
    assert is_zheji_candidate("26-计科-420-张三")
    assert is_zheji_candidate("26—软工—400—李四")
    assert not is_zheji_candidate("27-计科-420-张三")
    assert not is_zheji_candidate("26-计科-320-张三")


def test_parse_score_helpers() -> None:
    assert parse_zheruan_score("425-qbot") == 425
    assert parse_zheruan_score("26-计学-405-杨德曙[4]") is None
    assert parse_zheji_score("26-计学-405-杨德曙[4]") == 405
    assert parse_zheji_score("26-计学-320-杨德曙[4]") is None


def test_collect_candidates_prefers_card_then_nickname() -> None:
    members = [
        {"user_id": 1, "card": "420-张三", "nickname": "无效"},
        {"user_id": 2, "card": "", "nickname": "390-李四"},
        {"user_id": 3, "card": "bad", "nickname": "bad"},
    ]
    result = collect_candidates(members, is_zheruan_candidate)
    assert result == {1: "420-张三", 2: "390-李四"}


def test_build_overlap_text_contains_overlap_user() -> None:
    text = build_overlap_text(
        local_group_id=1084141833,
        zheji_group_id=924534632,
        local_candidates={10001: "420-张三", 10002: "390-李四"},
        zheji_candidates={10002: "26-计科-420-李四", 10003: "26-软工-410-王五"},
    )
    assert "重合人数：1" in text
    assert "10002" in text


def test_user_samples_match_respective_school_rules() -> None:
    # 浙软样例：分数-名字
    assert is_zheruan_candidate("425-qbot")
    assert not is_zheji_candidate("425-qbot")

    # 浙计样例：26-专业-分数-名字
    assert is_zheji_candidate("26-浙软-360-丁真[200]")
    assert not is_zheruan_candidate("26-浙软-360-丁真[200]")
