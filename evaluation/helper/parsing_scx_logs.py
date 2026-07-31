from pathlib import Path

from .parsing_sched_order import get_sched_log_name


def get_scx_log_filename(root: Path, plan_id: int, sched_command: str) -> str:
    """Returns the scheduler's userspace log filename"""
    sched_log_name = get_sched_log_name(root, sched_command)
    return f"plan{plan_id}_{sched_log_name}_run0_scx.logs"


def did_sched_fail(root: Path, plan_id: int, sched_command: str) -> bool:
    """Determines if a given sched_command failed during the measurement"""
    if sched_command == "EEVDF" or sched_command == "CFS":
        return False
    log_file = root / "logs" / get_scx_log_filename(root, plan_id, sched_command)

    if not log_file.exists():
        raise Exception("Log file does not exist.")

    reason = ""
    with open(log_file, "r") as f:
        for line in f:
            if "EXIT: runtime error" in line:
                return "Runtime Error"
            if "EXIT: runnable task stall" in line:
                return "Task Stall"
            if "DEBUG DUMP" in line:
                reason = "Unknown Reason"
    return reason
