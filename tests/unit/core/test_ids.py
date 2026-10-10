from triwitness.core.ids import is_ulid, new_run_id, new_task_id, new_ulid


def test_ulid_format_and_prefixes() -> None:
    assert is_ulid(new_ulid())
    assert new_task_id().startswith("t_") and is_ulid(new_task_id()[2:])
    assert new_run_id().startswith("r_") and is_ulid(new_run_id()[2:])


def test_ulid_sorts_by_time() -> None:
    a = new_ulid(1_000, b"\xff" * 10)
    b = new_ulid(1_001, b"\x00" * 10)
    assert a < b


def test_ulid_known_value() -> None:
    assert new_ulid(0, b"\x00" * 10) == "0" * 26
