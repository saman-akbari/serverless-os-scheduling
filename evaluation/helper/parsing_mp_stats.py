from pathlib import Path
from typing import Any

from .parsing_sched_order import (
    get_sched_log_name,
)


def is_empty_line(line: str) -> bool:
    return line == ""


def is_header_line(line: str) -> bool:
    parts = line.split()
    index = 1 if len(parts) == 12 else 2

    return parts[0] == "Linux" or parts[index] == "CPU"


def is_cpu_stat_line(line: str) -> bool:
    parts = line.split()
    if len(parts) == 12:
        # cpu stat line doesn't contain AM or PM in second column
        return int(parts[1]) in list(range(8))

    if len(parts) == 13:
        # cpu stat line contains AM or PM in second column
        return int(parts[2]) in list(range(8))

    raise Exception("Encountered unknown mpstat format")


def get_cpu_number(line: str) -> int:
    parts = line.split()
    index = 1 if len(parts) == 12 else 2

    return int(parts[index])


def get_idle_time(line: str) -> float:
    parts = line.split()
    index = 11 if len(parts) == 12 else 12

    return float(parts[index])


def get_sys_time(line: str) -> float:
    parts = line.split()
    index = 4 if len(parts) == 12 else 5
    return float(parts[index])


def get_usr_time(line: str) -> float:
    parts = line.split()
    index = 2 if len(parts) == 12 else 3
    return float(parts[index])


def get_nice_time(line: str) -> float:
    parts = line.split()
    index = 3 if len(parts) == 12 else 4
    return float(parts[index])


def get_steal_time(line: str) -> float:
    parts = line.split()
    index = 8 if len(parts) == 12 else 9
    return float(parts[index])


def get_log_timepoint(line: str) -> str:
    parts = line.split()
    return parts[0]


def parse_line(line: str, cpu_stats: dict):
    if is_empty_line(line):
        # ignore
        pass
    elif is_header_line(line):
        # ignore
        pass
    elif is_cpu_stat_line(line):
        cpu_number = get_cpu_number(line)
        idle_time = get_idle_time(line)
        sys_time = get_sys_time(line)
        nice_time = get_nice_time(line)
        usr_time = get_usr_time(line)
        steal_time = get_steal_time(line)
        log_timepoint = get_log_timepoint(line)
        if cpu_number not in cpu_stats:
            cpu_stats[cpu_number] = {
                "index": [],
                "usr": [],
                "nice": [],
                "sys": [],
                "steal": [],
                "idle": [],
            }
        cpu_stats[cpu_number]["usr"].append(usr_time)
        cpu_stats[cpu_number]["nice"].append(nice_time)
        cpu_stats[cpu_number]["sys"].append(sys_time)
        cpu_stats[cpu_number]["steal"].append(steal_time)
        cpu_stats[cpu_number]["idle"].append(idle_time)
        cpu_stats[cpu_number]["index"].append(log_timepoint)
    else:
        print("ENCOUNTERED UNKNOWN LINE")
        exit()


def parse_vm_stat_log_file(path: Path):
    cpu_stats = {}

    with open(path) as file:
        for line in file:
            parse_line(line.rstrip(), cpu_stats)

    return cpu_stats


def get_mpstat_path_by_cmd(root: Path, plan_id: int, sched_cmd: str):
    sched_log_name = get_sched_log_name(root, sched_cmd)

    return root / "logs" / f"plan{plan_id}_{sched_log_name}_run{0}_mpstat.logs"


def get_aggregated_stats(per_cpu_stats: dict[int, dict[str, list[Any]]]):
    # accumulate total time of cpus spent in user-mode and kernel mode
    cumulative_nice = 0
    cumulative_usr = 0
    cumulative_sys = 0
    cumulative_idle = 0
    cumulative_steal = 0

    for _, data in per_cpu_stats.items():
        assert len(data["index"]) == len(data["usr"])
        assert len(data["index"]) == len(data["nice"])
        assert len(data["index"]) == len(data["sys"])
        assert len(data["index"]) == len(data["idle"])
        assert len(data["index"]) == len(data["steal"])

        # mp stat shows percentage values spend in user, nice or sys mode for every second
        cumulative_usr += sum(data["usr"]) / 100
        cumulative_nice += sum(data["nice"]) / 100
        cumulative_sys += sum(data["sys"]) / 100
        cumulative_idle += sum(data["idle"]) / 100
        cumulative_steal += sum(data["steal"]) / 100

    return {
        "usr": cumulative_usr,
        "nice": cumulative_nice,
        "sys": cumulative_sys,
        "idle": cumulative_idle,
        "steal": cumulative_steal,
    }


def get_accumulated_vm_stats_by_cmd(root: Path, plan_id: str, sched_cmd: str):
    mpstat_path = get_mpstat_path_by_cmd(root, int(plan_id), sched_cmd)
    per_cpu_stats = parse_vm_stat_log_file(mpstat_path)
    sched_data = get_aggregated_stats(per_cpu_stats)
    return sched_data
