import pytest

from qbot.repository import ScoreRepository


@pytest.mark.asyncio
async def test_command_usage_counts(tmp_path) -> None:
    repo = ScoreRepository(tmp_path / "qbot.sqlite3")
    await repo.init()

    group_id = 1084141833
    user_id = 2038482714
    await repo.log_command_usage(group_id, user_id, "rank", "run")
    await repo.log_command_usage(group_id, user_id, "rank", "run")
    await repo.log_command_usage(group_id, user_id, "set", "run")
    await repo.log_command_usage(group_id, user_id, "rank", "help")

    run_counts = await repo.get_command_usage_counts(group_id, user_id, action="run")
    help_counts = await repo.get_command_usage_counts(group_id, user_id, action="help")

    assert run_counts == [("rank", 2), ("set", 1)]
    assert help_counts == [("rank", 1)]
