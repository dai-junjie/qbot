from qbot.parser import parse_member_card


def test_parse_valid_dash() -> None:
    item = parse_member_card("420-张三")
    assert item is not None
    assert item.score == 420
    assert item.name == "张三"


def test_parse_valid_em_dash() -> None:
    item = parse_member_card("499—李四")
    assert item is not None
    assert item.score == 499
    assert item.name == "李四"


def test_parse_out_of_range() -> None:
    assert parse_member_card("349-王五") is None
    assert parse_member_card("501-赵六") is None


def test_parse_invalid_format() -> None:
    assert parse_member_card("420 张三") is None
