import re

from qbot.config import Settings


def _extract_group_id_from_log(line: str) -> int | None:
    m = re.search(r"\[群:(\d+)\]", line)
    if not m:
        return None
    return int(m.group(1))


def test_read_enabled_groups_from_env_file(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("QBOT_ENABLED_GROUPS=1084141833,747378973\n", encoding="utf-8")

    settings = Settings(_env_file=env_path)
    assert settings.enabled_groups == ["1084141833", "747378973"]


def test_simulated_log_group_matches_whitelist(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("QBOT_ENABLED_GROUPS=1084141833\n", encoding="utf-8")
    settings = Settings(_env_file=env_path)
    allow = set(settings.enabled_groups)

    hit_log = (
        "OneBot V11 ... [message.group.normal]: Message ... "
        "from 123@[群:1084141833] '/rank'"
    )
    miss_log = (
        "OneBot V11 ... [message.group.normal]: Message ... "
        "from 123@[群:747378973] '/rank'"
    )

    hit_group = _extract_group_id_from_log(hit_log)
    miss_group = _extract_group_id_from_log(miss_log)

    assert hit_group is not None and str(hit_group) in allow
    assert miss_group is not None and str(miss_group) not in allow
