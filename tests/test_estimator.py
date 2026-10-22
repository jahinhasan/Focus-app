"""Duration estimation, leakage safety, analytics (spec N.9, J)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import estimator as fe


def _mk(data, title, subject, difficulty, duration, actual, created, completed):
    import logic
    logic.add_task_logic(data, title, duration=duration, subject=subject, difficulty=difficulty)
    t = data["tasks"][-1]
    t["created_at"] = created
    t["status"] = "done"
    t["actual_minutes"] = actual
    t["completed_at"] = completed
    t["updated_at"] = completed[:10]
    return t


def test_no_history_uses_default_not_claimed_learned(data):
    import logic
    logic.add_task_logic(data, "New task", duration=60)
    info = fe.estimate_minutes(data, data["tasks"][0])
    assert info["minutes"] == round(60 * fe.DEFAULT_RATIO)
    assert not info["reliable"] and info["samples"] == 0
    assert "no history" in info["basis"]


def test_learns_subject_pattern_with_enough_samples(data):
    for i in range(3):
        _mk(data, f"AI hw {i}", "AI", 2, 60, 120, f"2026-10-{10+i:02d}", f"2026-10-{11+i:02d}")
    import logic
    logic.add_task_logic(data, "AI essay", duration=60, subject="AI")
    info = fe.estimate_minutes(data, data["tasks"][-1])
    assert info["reliable"]
    assert info["minutes"] == 120
    assert "subject" in info["basis"]


def test_sparse_group_falls_back_and_admits_it(data):
    # only 2 samples for the subject -> below MIN_SAMPLES -> global default path
    for i in range(2):
        _mk(data, f"AI hw {i}", "AI", 2, 60, 120, f"2026-10-{10+i:02d}", f"2026-10-{11+i:02d}")
    import logic
    logic.add_task_logic(data, "AI quiz", duration=60, subject="AI")
    info = fe.estimate_minutes(data, data["tasks"][-1])
    # 2 samples < MIN_SAMPLES(3): global median has only 2 samples too -> default
    assert info["minutes"] == round(60 * fe.DEFAULT_RATIO)
    assert not info["reliable"]
    assert "default" in info["basis"] or "samples" in info["basis"]


def test_difficulty_grouping(data):
    for i in range(3):
        _mk(data, f"Hard {i}", None, 3, 60, 180, f"2026-10-{10+i:02d}", f"2026-10-{11+i:02d}")
    import logic
    logic.add_task_logic(data, "Hard thing", duration=60, difficulty=3)
    info = fe.estimate_minutes(data, data["tasks"][-1])
    assert info["reliable"] and info["minutes"] == 180


def test_no_data_leakage_from_future(data):
    # subject pattern exists BEFORE the task; future completions must not count
    for i in range(3):
        _mk(data, f"AI hw {i}", "AI", 2, 60, 120, "2026-11-01", "2026-11-02")  # future
    import logic
    logic.add_task_logic(data, "Early task", duration=60, subject="AI")
    t = data["tasks"][-1]
    t["created_at"] = "2026-10-01"
    info = fe.estimate_minutes(data, t)
    assert not info["reliable"], "future observations must not influence past predictions"
    assert info["minutes"] == round(60 * fe.DEFAULT_RATIO)


def test_analytics_metrics(data):
    _mk(data, "A", "AI", 2, 60, 90, "2026-10-01", "2026-10-02T09:00:00")   # 30 over
    _mk(data, "B", "AI", 2, 60, 60, "2026-10-03", "2026-10-04T09:00:00")   # exact
    res = fe.estimation_analytics(data)
    assert res["n"] == 2
    assert res["mae_minutes"] == 15.0
    assert res["on_time_rate"] == 0.5
    assert "AI" in res["by_subject"]
    comp = fe.completion_analytics(data)
    assert comp["active_days"] >= 0


def test_archived_tasks_still_learned(data):
    _mk(data, "Archived learner", "AI", 2, 60, 150, "2026-10-01", "2026-10-02T09:00:00")
    data["archived_tasks"] = [data["tasks"].pop()]
    res = fe.estimation_analytics(data)
    assert res["n"] == 1
    import logic
    logic.add_task_logic(data, "Now task", duration=60, subject="AI")
    info = fe.estimate_minutes(data, data["tasks"][0])
    assert info["samples"] == 1  # sees the archived observation
