# ==================== ESTIMATOR.PY ====================
# Transparent duration estimation from productivity history.
#
# Baseline approach (deliberately lightweight, no ML dependency):
# - Learn a ratio of actual_minutes / estimated duration ("time realism") from
#   completed tasks that have BOTH an estimate (`duration`) and an actual
#   measurement (`actual_minutes`).
# - Ratios are grouped by subject (exact) and difficulty; a group is only used
#   when it has MIN_SAMPLES observations - otherwise fall back to the global
#   median ratio, then to a fixed default. Sparse data is reported as such.
# - Leakage safety: an estimate for task T only uses tasks COMPLETED BEFORE T
#   (completed_at < T.created_at) - future outcomes never influence past
#   predictions.

from statistics import median

MIN_SAMPLES = 3           # per-group sample floor
DEFAULT_RATIO = 1.15      # students typically underestimate by ~15%
MAX_RATIO = 3.0           # clamp outliers
MIN_MINUTES = 10          # ignore trivial measurements
MAX_MINUTES = 8 * 60


def _valid_observation(task):
    est, act = task.get("duration"), task.get("actual_minutes")
    if not isinstance(est, (int, float)) or not isinstance(act, (int, float)):
        return False
    if est < MIN_MINUTES or act < MIN_MINUTES:
        return False
    return est <= MAX_MINUTES and act <= MAX_MINUTES


def collect_observations(data):
    """All usable (subject, difficulty, ratio, completed_at, created_at) tuples.

    Sources: active tasks with estimate+actual, plus the archived history.
    """
    obs = []
    tasks = list(data.get("tasks", [])) + list(data.get("archived_tasks", []))
    for t in tasks:
        if not isinstance(t, dict) or t.get("status") != "done":
            continue
        if not _valid_observation(t):
            continue
        ratio = float(t["actual_minutes"]) / float(t["duration"])
        if ratio <= 0 or ratio > MAX_RATIO * 2:
            continue
        obs.append({
            "subject": t.get("subject"),
            "difficulty": t.get("difficulty"),
            "ratio": ratio,
            "completed_at": t.get("completed_at") or "",
            "created_at": t.get("created_at") or "",
            "task_id": t.get("id"),
        })
    return obs


def _group_ratios(obs, key_fn):
    groups = {}
    for o in obs:
        k = key_fn(o)
        if k is None:
            continue
        groups.setdefault(k, []).append(min(o["ratio"], MAX_RATIO))
    return groups


def estimate_minutes(data, task, settings=None, ref_created_at=None):
    """Estimate actual duration (minutes) for a task.

    Returns dict: {minutes, basis, samples, reliable}.
    - basis explains the decision (interpretable, no black box).
    - reliable=False means data is sparse: the number is a sensible default,
      NOT a learned pattern (the UI labels it as such).
    """
    est = task.get("duration") or task.get("estimated_minutes")
    if not isinstance(est, (int, float)) or est <= 0:
        return {"minutes": None, "basis": "no estimate available",
                "samples": 0, "reliable": False}
    est = float(est)

    obs = collect_observations(data)
    # Leakage guard: only observations completed before this task was created
    if ref_created_at or task.get("created_at"):
        cutoff = ref_created_at or task.get("created_at")
        obs = [o for o in obs if (o["completed_at"] or "9999") <= (cutoff or "9999")]

    if not obs:
        return {"minutes": int(round(est * DEFAULT_RATIO)),
                "basis": f"default realism x{DEFAULT_RATIO} (no history yet)",
                "samples": 0, "reliable": False}

    global_ratio = median([o["ratio"] for o in obs])

    # 1. subject + difficulty group
    subj, diff = task.get("subject"), task.get("difficulty")
    if subj is not None and diff is not None:
        g = [o["ratio"] for o in obs
             if o["subject"] == subj and o["difficulty"] == diff]
        if len(g) >= MIN_SAMPLES:
            r = median(g)
            return {"minutes": int(round(est * r)), "basis":
                    f"median ratio {r:.2f}x for {len(g)} tasks of this subject+difficulty",
                    "samples": len(g), "reliable": True}

    # 2. subject group
    if subj is not None:
        g = [o["ratio"] for o in obs if o["subject"] == subj]
        if len(g) >= MIN_SAMPLES:
            r = median(g)
            return {"minutes": int(round(est * r)), "basis":
                    f"median ratio {r:.2f}x for {len(g)} tasks of subject '{subj}'",
                    "samples": len(g), "reliable": True}

    # 3. difficulty group
    if diff is not None:
        g = [o["ratio"] for o in obs if o["difficulty"] == diff]
        if len(g) >= MIN_SAMPLES:
            r = median(g)
            return {"minutes": int(round(est * r)), "basis":
                    f"median ratio {r:.2f}x for {len(g)} tasks of difficulty {diff}",
                    "samples": len(g), "reliable": True}

    # 4. global median (only if it has enough total samples)
    if len(obs) >= MIN_SAMPLES:
        return {"minutes": int(round(est * global_ratio)),
                "basis": f"overall median ratio {global_ratio:.2f}x across {len(obs)} completed tasks",
                "samples": len(obs), "reliable": True}

    return {"minutes": int(round(est * DEFAULT_RATIO)),
            "basis": f"default realism x{DEFAULT_RATIO} (only {len(obs)} samples)",
            "samples": len(obs), "reliable": False}


def estimation_analytics(data):
    """Estimated-vs-actual analytics for the report view.

    Returns {n, mae_minutes, mean_error_ratio, on_time_rate, by_subject}.
    """
    obs = collect_observations(data)
    if not obs:
        return {"n": 0, "mae_minutes": None, "mean_error_ratio": None,
                "on_time_rate": None, "by_subject": {}}

    tasks = list(data.get("tasks", [])) + list(data.get("archived_tasks", []))
    by_id = {t.get("id"): t for t in tasks if isinstance(t, dict)}

    errs, ratios, on_time = [], [], 0
    by_subject = {}
    for o in obs:
        t = by_id.get(o["task_id"], {})
        est = float(t.get("duration") or 0)
        act = float(t.get("actual_minutes") or 0)
        if est <= 0:
            continue
        errs.append(abs(act - est))
        ratios.append(act / est)
        if act <= est:
            on_time += 1
        subj = o["subject"] or "Unassigned"
        s = by_subject.setdefault(subj, {"n": 0, "error_sum": 0.0})
        s["n"] += 1
        s["error_sum"] += abs(act - est)

    by_subject = {k: {"n": v["n"], "mae_minutes": round(v["error_sum"] / v["n"], 1)}
                  for k, v in by_subject.items()}
    return {
        "n": len(errs),
        "mae_minutes": round(sum(errs) / len(errs), 1) if errs else None,
        "mean_error_ratio": round(sum(ratios) / len(ratios), 2) if ratios else None,
        "on_time_rate": round(on_time / len(errs), 2) if errs else None,
        "by_subject": by_subject,
    }


def completion_analytics(data):
    """Completion + adherence summary from history and tasks.

    Returns {completed_total, tasks_total, done_ratio, focus_minutes_total,
             active_days}.
    """
    hist = data.get("history", {})
    completed = sum(h.get("completed", 0) for h in hist.values())
    totals = sum(h.get("total", 0) for h in hist.values())
    focus = sum(h.get("focus_minutes", 0) for h in hist.values())
    archived = data.get("archived_tasks", [])
    return {
        "completed_total": completed + len(archived),
        "tasks_total": max(totals, len(data.get("tasks", []))),
        "done_ratio": round((completed + len(archived)) / totals, 2) if totals else None,
        "focus_minutes_total": focus,
        "active_days": len(hist),
    }
