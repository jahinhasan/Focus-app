from datetime import date

LEVEL_XP = 100
TARGET_DAYS = 7


def today():
    return date.today().isoformat()


def xp_per_task(task_count):
    if task_count == 0:
        return 0
    return LEVEL_XP / (TARGET_DAYS * task_count)
