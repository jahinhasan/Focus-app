# ==================== TOOLS/SUBJECTS.PY ====================
# Subject & routine tools: detection with confidence thresholds, vault CRUD,
# routine reads, and explicit subject assignment (ask-don't-guess).

from logic import add_subject, add_task_logic, update_task_logic
from focus_agent import subjects as fsubjects
from focus_agent.repository import SubjectRepository
from focus_agent.tools.base import (
    ToolResult, tool, find_task_fuzzy,
)


@tool("list_subjects", "List known subjects and where they come from.", {})
def tool_list_subjects(data, args, ctx):
    known = fsubjects.get_known_subjects(data)
    items = [{"name": n, "source": s} for n, s in sorted(known.items())]
    return ToolResult(True, "list_subjects", message=f"{len(items)} subject(s)",
                      data={"subjects": items})


@tool("create_subject", "Create a new subject in the Vault.",
      {"name": {"type": "str", "required": True, "max": 120}},
      permission="write", requires_confirmation=True)
def tool_create_subject(data, args, ctx):
    name = args["name"]
    if add_subject(data, name):
        return ToolResult(True, "create_subject", message=f"Created subject '{name}'")
    return ToolResult(True, "create_subject", message=f"Subject '{name}' already exists",
                      data={"existed": True})


@tool("update_subject", "Rename a vault subject and/or add keyword aliases used by detection.",
      {"subject": {"type": "str", "required": True, "max": 120},
       "new_name": {"type": "str", "max": 120},
       "keywords": {"type": "str_list"}},
      permission="write")
def tool_update_subject(data, args, ctx):
    repo = SubjectRepository(data)
    names = {s.name.lower() for s in repo.list()}
    subj = next((s for s in repo.list() if s.name.lower() == args["subject"].lower()), None)
    if not subj:
        return ToolResult(False, "update_subject",
                          error=f"No subject named {args['subject']!r}; known: {sorted(names)}")
    notes = []
    if args.get("keywords"):
        repo.set_keywords(subj.name, args["keywords"])
        notes.append(f"keywords now {args['keywords']}")
    if args.get("new_name") and args["new_name"].lower() != subj.name.lower():
        old = subj.name
        repo.rename(old, args["new_name"])
        notes.append(f"renamed '{old}' -> '{args['new_name']}'")
    if not notes:
        return ToolResult(False, "update_subject", error="Nothing to update")
    return ToolResult(True, "update_subject", message=f"Subject updated: " + "; ".join(notes),
                      data={"subject": args.get("new_name") or subj.name,
                            "keywords": args.get("keywords")})


@tool("detect_task_subject", "Classify the subject of a task or free-text mention from the vault and class routine. Read-only; returns ranked candidates with confidence.",
      {"mention": {"type": "str", "max": 200},
       "task_ref": {"type": "str", "max": 200}})
def tool_detect_task_subject(data, args, ctx):
    mention = args.get("mention")
    if not mention and args.get("task_ref"):
        t = find_task_fuzzy(data, args["task_ref"])
        if not t:
            return ToolResult(False, "detect_task_subject",
                              error=f"No task matching {args['task_ref']!r}")
        mention = t.get("title") or ""
        if t.get("notes"):
            mention += " " + t["notes"]
    if not mention:
        return ToolResult(False, "detect_task_subject",
                          error="Provide 'mention' (text) or 'task_ref'")
    match = fsubjects.match_subject(mention, data)
    known = fsubjects.get_known_subjects(data)
    # ranked candidates: best match first, then any subject sharing a keyword
    ranked = []
    if match:
        ranked.append({"subject": match["subject"], "confidence": match["confidence"],
                       "source": match.get("source"), "matched_on": match.get("matched_on"),
                       "auto": bool(match.get("auto"))})
    low = mention.lower()
    for name in sorted(known):
        if match and name == match["subject"]:
            continue
        words = [w for w in name.lower().split() if len(w) > 3]
        hits = sum(1 for w in words if w in low)
        if words and hits:
            ranked.append({"subject": name, "confidence": round(min(0.75, 0.35 * hits), 2),
                           "source": known[name], "matched_on": "keyword",
                           "auto": False})
    verdict = "confident" if (match and match.get("auto")) else \
              ("uncertain - confirm with the user" if match else "no match")
    return ToolResult(True, "detect_task_subject",
                      message=f"{verdict}: {ranked[0]['subject'] if ranked else 'none'}",
                      data={"mention": mention, "candidates": ranked[:5],
                            "verdict": verdict})


@tool("assign_subject", "Attach a task to a subject (fuzzy match must be confident).",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "subject": {"type": "str", "required": True, "max": 120}},
      permission="write")
def tool_assign_subject(data, args, ctx):
    t = find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "assign_subject", error=f"No task matching {args['task_ref']!r}")
    m = fsubjects.match_subject(args["subject"], data)
    if not m:
        return ToolResult(False, "assign_subject",
                          error=(f"No subject matches '{args['subject']}'. Create it first "
                                 "(I will ask for confirmation) or check the spelling."))
    update_task_logic(data, t["id"], subject=m["subject"])
    conf = "" if m["auto"] else f" (low confidence {m['confidence']:.2f} - verify)"
    return ToolResult(True, "assign_subject",
                      message=f"'{t.get('title')}' assigned to subject '{m['subject']}'{conf}",
                      data={"task_id": t["id"], "subject": m["subject"],
                            "confidence": m["confidence"]})


@tool("get_routine", "Read the weekly class routine.", {"day": {"type": "str"}})
def _tool_get_routine(data, args, ctx):
    week = fsubjects.subjects_for_routine(data)
    if args.get("day"):
        day = args["day"].lower()[:3]
        if day not in week:
            return ToolResult(False, "get_routine", error="day must be mon..sun")
        return ToolResult(True, "get_routine", message=f"{len(week[day])} class(es) on {day}",
                          data={"day": day, "classes": week[day]})
    total = sum(len(v) for v in week.values())
    return ToolResult(True, "get_routine", message=f"{total} classes/week",
                      data={"week": week})


@tool("add_class", "Add a recurring class to the routine.",
      {"title": {"type": "str", "required": True, "max": 120},
       "days": {"type": "str_list", "required": True},
       "start": {"type": "hhmm", "required": True},
       "end": {"type": "hhmm", "required": True}},
      permission="write")
def tool_add_class(data, args, ctx):
    days = [d for d in (str(x).lower()[:3] for x in args["days"])
            if d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
    if not days:
        return ToolResult(False, "add_class", error="days must include at least one of mon..sun")
    if args["start"] >= args["end"]:
        return ToolResult(False, "add_class", error="start must be before end")
    sch = {"days": sorted(set(days)), "start": args["start"], "end": args["end"]}
    task = add_task_logic(data, args["title"], category="class", days=sch["days"],
                          schedule=sch, subject=args["title"])
    return ToolResult(True, "add_class",
                      message=f"Added class '{args['title']}' {', '.join(sch['days'])} "
                              f"{args['start']}-{args['end']}",
                      data={"class_id": task["id"]})
