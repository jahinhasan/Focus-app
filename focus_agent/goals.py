# ==================== GOALS.PY ====================
# Long-term goals + editable milestones + progress tracking.
# Persisted under data["goals"] (schema v3). All CRUD is validated; the LLM
# can propose goal structures but only through the validated tool layer.

import uuid
from datetime import date

from logic import save_data
from focus_agent import dates as fdates
from focus_agent.schemas import clean_str, valid_date

GOAL_STATUSES = ("active", "paused", "done")


def _new_goal(title, description=None, target_date=None, subject=None):
    return {
        "id": str(uuid.uuid4()),
        "title": clean_str(title, 200),
        "description": clean_str(description, 2000),
        "subject": clean_str(subject, 120),
        "status": "active",
        "target_date": valid_date(target_date),
        "created_at": fdates.today_str(),
        "updated_at": fdates.today_str(),
        "milestones": [],
    }


def _new_milestone(title, target_date=None, estimated_minutes=None):
    return {
        "id": str(uuid.uuid4()),
        "title": clean_str(title, 200),
        "done": False,
        "target_date": valid_date(target_date),
        "estimated_minutes": (estimated_minutes if isinstance(estimated_minutes, (int, float))
                              and 0 < estimated_minutes <= 10_000 else None),
        "created_at": fdates.today_str(),
    }


def get_goal(data, goal_id):
    return next((g for g in data.get("goals", []) if g.get("id") == goal_id), None)


def find_goal_by_title(data, title_fragment):
    frag = (title_fragment or "").lower().strip()
    if not frag:
        return None
    for g in data.get("goals", []):
        if frag in (g.get("title") or "").lower():
            return g
    return None


def add_goal(data, title, description=None, target_date=None, subject=None,
             milestones=None):
    """Create a goal. Returns (goal_dict, error_or_None)."""
    title = clean_str(title, 200)
    if not title:
        return None, "Goal needs a title"
    if target_date and not valid_date(target_date):
        return None, "target_date must be YYYY-MM-DD"
    goal = _new_goal(title, description, target_date, subject)
    for ms in (milestones or [])[:30]:
        if isinstance(ms, dict) and clean_str(ms.get("title"), 200):
            goal["milestones"].append(_new_milestone(
                ms["title"], ms.get("target_date"), ms.get("estimated_minutes")))
    data.setdefault("goals", []).append(goal)
    save_data(data)
    return goal, None


def update_goal(data, goal_id, **fields):
    """Edit editable goal fields. Returns (ok, error)."""
    goal = get_goal(data, goal_id)
    if not goal:
        return False, "Goal not found"
    allowed = {"title", "description", "target_date", "subject", "status"}
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "status" and v not in GOAL_STATUSES:
            return False, f"status must be one of {GOAL_STATUSES}"
        if k == "target_date":
            v = valid_date(v)
            if not v:
                return False, "target_date must be YYYY-MM-DD"
        if k in ("title", "description", "subject"):
            v = clean_str(v, 2000)
            if not v:
                continue
        goal[k] = v
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return True, None


def delete_goal(data, goal_id):
    """Remove a goal. Tasks linked to it are unlinked, NOT deleted."""
    before = len(data.get("goals", []))
    data["goals"] = [g for g in data.get("goals", []) if g.get("id") != goal_id]
    if len(data["goals"]) == before:
        return False
    for t in data.get("tasks", []):
        if t.get("goal_id") == goal_id:
            t["goal_id"] = None
    save_data(data)
    return True


def add_milestone(data, goal_id, title, target_date=None, estimated_minutes=None):
    goal = get_goal(data, goal_id)
    if not goal:
        return None, "Goal not found"
    title = clean_str(title, 200)
    if not title:
        return None, "Milestone needs a title"
    ms = _new_milestone(title, target_date, estimated_minutes)
    goal["milestones"].append(ms)
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return ms, None


def update_milestone(data, goal_id, milestone_id, done=None, title=None,
                     target_date=None):
    goal = get_goal(data, goal_id)
    if not goal:
        return False, "Goal not found"
    ms = next((m for m in goal["milestones"] if m.get("id") == milestone_id), None)
    if not ms:
        return False, "Milestone not found"
    if done is not None:
        ms["done"] = bool(done)
    if title:
        ms["title"] = clean_str(title, 200) or ms["title"]
    if target_date is not None:
        ms["target_date"] = valid_date(target_date)
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return True, None


def delete_milestone(data, goal_id, milestone_id):
    goal = get_goal(data, goal_id)
    if not goal:
        return False
    before = len(goal["milestones"])
    goal["milestones"] = [m for m in goal["milestones"] if m.get("id") != milestone_id]
    if len(goal["milestones"]) == before:
        return False
    save_data(data)
    return True


def goal_progress(data, goal):
    """Progress metrics for one goal: milestone completion + task effort done.

    Returns {milestones_done, milestones_total, percent, tasks_done,
             tasks_total, overdue_milestones, next_milestone, blocked_by}.
    """
    today_iso = fdates.today_str()
    mss = goal.get("milestones", [])
    ms_done = sum(1 for m in mss if m.get("done"))
    tasks = [t for t in data.get("tasks", []) if t.get("goal_id") == goal.get("id")]
    tasks_done = sum(1 for t in tasks if t.get("status") == "done")

    overdue = [m for m in mss
               if not m.get("done") and m.get("target_date") and m["target_date"] < today_iso]
    upcoming = [m for m in mss if not m.get("done")]
    upcoming.sort(key=lambda m: m.get("target_date") or "9999-12-31")
    next_ms = upcoming[0] if upcoming else None

    ms_pct = (ms_done / len(mss) * 100) if mss else None
    task_pct = (tasks_done / len(tasks) * 100) if tasks else None
    parts = [p for p in (ms_pct, task_pct) if p is not None]
    percent = round(sum(parts) / len(parts)) if parts else (0 if mss or tasks else None)

    target = goal.get("target_date")
    goal_overdue = bool(target and target < today_iso and (percent is None or percent < 100))

    return {
        "milestones_done": ms_done,
        "milestones_total": len(mss),
        "percent": percent,
        "tasks_done": tasks_done,
        "tasks_total": len(tasks),
        "overdue": goal_overdue,
        "overdue_milestones": [{"id": m["id"], "title": m["title"],
                                "target_date": m["target_date"]} for m in overdue],
        "next_milestone": ({"id": next_ms["id"], "title": next_ms["title"],
                            "target_date": next_ms.get("target_date")}
                           if next_ms else None),
    }


DOMAIN_ROADMAPS = {
    "networking": [
        ("1. Network Fundamentals, OSI & TCP/IP 5-Layer Model", 0.16),
        ("2. IPv4/IPv6 Addressing, Subnetting, CIDR & VLSM Practice", 0.18),
        ("3. Data Link Layer, Ethernet Switching, VLANs & STP", 0.16),
        ("4. Routing Protocols (Static Routing, OSPF, BGP) & Packet Tracer Labs", 0.18),
        ("5. Transport Layer (TCP/UDP, 3-Way Handshake, Ports) & Wireshark Lab", 0.16),
        ("6. Application Layer (DNS, HTTP/S, DHCP, SSH), Firewalls & Socket Mini-Project", 0.16),
    ],
    "python": [
        ("1. Python Syntax, Variables, Data Types, Conditionals & Loops", 0.18),
        ("2. Functions, Modules, Lists, Dictionaries, Sets & File I/O", 0.20),
        ("3. Object-Oriented Programming (Classes, Inheritance) & Exceptions", 0.20),
        ("4. Virtual Environments, External Packages, REST APIs & Pytest", 0.20),
        ("5. Capstone Project — Build & Package a Complete Python App", 0.22),
    ],
    "database": [
        ("1. Relational Model, ER Diagrams & Database Schema Design", 0.18),
        ("2. Core SQL — SELECT, JOINs, Group By, Aggregations & Subqueries", 0.22),
        ("3. Database Normalization (1NF, 2NF, 3NF, BCNF) & Indexing", 0.20),
        ("4. Transactions, ACID Properties, Concurrency & Query Optimization", 0.20),
        ("5. Capstone Project — Full Database Application with Stored Procedures", 0.20),
    ],
    "machine_learning": [
        ("1. Python Data Stack (NumPy, Pandas, Matplotlib) & Math Foundations", 0.18),
        ("2. Supervised Learning — Linear/Logistic Regression & Decision Trees", 0.22),
        ("3. Model Evaluation, Feature Engineering, Random Forest & XGBoost", 0.20),
        ("4. Unsupervised Learning (K-Means, PCA) & Neural Network Basics", 0.20),
        ("5. End-to-End ML Project — Data Pipeline, Training & Model Deployment", 0.20),
    ],
    "dsa": [
        ("1. Time/Space Complexity (Big-O), Arrays, Strings & Two Pointers", 0.18),
        ("2. Hash Maps, Linked Lists, Stacks, Queues & Recursion", 0.20),
        ("3. Binary Trees, Binary Search Trees (BST), Heaps & Priority Queues", 0.20),
        ("4. Graphs (BFS, DFS, Shortest Path, Topological Sort) & Greedy", 0.20),
        ("5. Dynamic Programming (1D/2D DP) & Timed Problem-Solving Practice", 0.22),
    ],
    "web": [
        ("1. Semantic HTML5, Modern CSS3, Flexbox, Grid & Responsive UI", 0.18),
        ("2. JavaScript ES6+, DOM Manipulation, Async/Await & Fetch API", 0.22),
        ("3. Frontend Framework (React Components, State, Hooks & Routing)", 0.22),
        ("4. Backend REST APIs, Authentication & Database Integration", 0.20),
        ("5. Full-Stack Portfolio Project & Live Cloud Deployment", 0.18),
    ],
    "os": [
        ("1. OS Kernel Concepts, Processes, Threads, System Calls & Linux CLI", 0.20),
        ("2. CPU Scheduling Algorithms (FCFS, SJF, Round Robin, Priority)", 0.20),
        ("3. Process Synchronization, Mutexes, Semaphores & Deadlocks", 0.20),
        ("4. Memory Management, Paging, Segmentation & Virtual Memory", 0.20),
        ("5. File Systems, Disk Scheduling & Custom Shell Mini-Project", 0.20),
    ],
    "security": [
        ("1. Linux & Networking Fundamentals for Security, Bash & Permissions", 0.20),
        ("2. Cryptography Basics, Hashing, TLS/HTTPS & Authentication", 0.20),
        ("3. Web Application Security & OWASP Top 10 (SQLi, XSS, CSRF Labs)", 0.22),
        ("4. Network Reconnaissance, Nmap, Wireshark & Vulnerability Scanning", 0.18),
        ("5. System Hardening, Firewalls, Log Analysis & Beginner CTF Practice", 0.20),
    ],
    "robotics": [
        ("1. Electronics Basics, Microcontrollers (Arduino/ESP32) & Sensors", 0.20),
        ("2. Motor Drivers, PWM, Actuators & Embedded C/Python Programming", 0.20),
        ("3. Robot Kinematics, Odometry & PID Control Loops", 0.20),
        ("4. ROS (Robot Operating System) Nodes, Topics & Simulation", 0.20),
        ("5. Autonomous Obstacle-Avoiding / Line-Following Robot Project", 0.20),
    ],
}


def _match_domain_phases(goal_title: str):
    low = (goal_title or "").lower()
    if any(k in low for k in ("network", "networking", "ccna", "data comm", "tcp", "osi", "subnet")):
        return DOMAIN_ROADMAPS["networking"]
    if any(k in low for k in ("machine learning", "deep learning", "artificial intelligence", "ml", "neural", "data science")):
        return DOMAIN_ROADMAPS["machine_learning"]
    if any(k in low for k in ("database", "dbms", "sql", "postgres", "mysql", "mongodb")):
        return DOMAIN_ROADMAPS["database"]
    if any(k in low for k in ("dsa", "data structure", "algorithm", "leetcode", "competitive programming")):
        return DOMAIN_ROADMAPS["dsa"]
    if any(k in low for k in ("web", "react", "frontend", "fullstack", "full stack", "javascript", "html", "nextjs", "node")):
        return DOMAIN_ROADMAPS["web"]
    if any(k in low for k in ("operating system", "linux", "kernel")):
        return DOMAIN_ROADMAPS["os"]
    if any(k in low for k in ("cyber", "security", "hacking", "pentest", "ctf")):
        return DOMAIN_ROADMAPS["security"]
    if any(k in low for k in ("robot", "robotics", "arduino", "ros", "iot")):
        return DOMAIN_ROADMAPS["robotics"]
    if "python" in low:
        return DOMAIN_ROADMAPS["python"]
    return None


def _llm_or_topic_phases(goal_title: str, provider=None):
    """Try generating 5 topic-specific milestones via LLM (+ online summary if available)."""
    clean_topic = (goal_title or "the subject").strip()
    if provider is not None and getattr(provider, "name", "none") not in ("none", "offline"):
        try:
            from focus_agent.llm import fetch_online_topic_summary
            web_ctx = fetch_online_topic_summary(clean_topic)
            ctx_line = f"\nOnline reference context: {web_ctx}" if web_ctx else ""
            res = provider.chat_json(
                system=(
                    "You are an academic curriculum designer. Return ONLY a JSON object "
                    '{"milestones": ["1. ...", "2. ...", "3. ...", "4. ...", "5. ..."]} '
                    "with 5 concrete, progressive, topic-specific learning milestones."
                ),
                user=f"Create a 5-step study roadmap for: {clean_topic}.{ctx_line}",
                temperature=0.0,
                max_tokens=600,
            )
            ms_list = res.get("milestones") if isinstance(res, dict) else None
            if isinstance(ms_list, list) and len(ms_list) >= 4:
                valid_ms = [str(x).strip() for x in ms_list[:6] if str(x).strip()]
                if len(valid_ms) >= 4:
                    share = round(1.0 / len(valid_ms), 2)
                    return [(m_title, share) for m_title in valid_ms]
        except Exception:
            pass

    return [
        (f"1. Core Concepts & Foundations of {clean_topic}", 0.20),
        (f"2. Essential Tools, Syntax & Hands-On Exercises in {clean_topic}", 0.20),
        (f"3. Intermediate Techniques & Problem Solving in {clean_topic}", 0.20),
        (f"4. Applied Mini-Project & Practical Implementation ({clean_topic})", 0.20),
        (f"5. Advanced Topics, Review & Capstone Project ({clean_topic})", 0.20),
    ]


def generate_roadmap_draft(goal_title, weeks=6, hours_per_week=8, start_date=None,
                           assumptions=None, provider=None):
    """Build an EDITABLE, topic-specific roadmap draft with concrete milestones."""
    try:
        weeks = max(2, min(int(weeks), 26))
        hours_per_week = max(1, min(int(hours_per_week), 40))
    except (TypeError, ValueError):
        return None, "weeks and hours_per_week must be numbers"
    start = start_date or fdates.today_str()
    try:
        d0 = date.fromisoformat(start)
    except ValueError:
        return None, "start_date must be YYYY-MM-DD"

    from datetime import timedelta
    total_hours = weeks * hours_per_week
    phases = _match_domain_phases(goal_title) or _llm_or_topic_phases(goal_title, provider=provider)
    milestones = []
    for i, (phase, share) in enumerate(phases):
        end = d0 + timedelta(days=max(3, int(round((i + 1) * (weeks * 7) / len(phases)))))
        hrs = max(2, int(round(total_hours * share)))
        milestones.append({
            "title": f"{phase} (~{hrs}h)",
            "target_date": end.isoformat(),
            "estimated_minutes": hrs * 60,
        })
    return {
        "goal_title": goal_title,
        "milestones": milestones,
        "assumptions": assumptions or [
            f"{weeks}-week study plan at ~{hours_per_week}h/week (~{total_hours}h total) starting {start}",
            "All milestones are saved in your Goals & Roadmaps tab — you can check them off or convert any milestone into a daily task.",
        ],
    }, None
