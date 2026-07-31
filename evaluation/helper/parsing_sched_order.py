from pathlib import Path


def get_sched_command_order(result_root_path: Path) -> list[str]:
    """Get a list of the used scheduling commands ordered by their usage in the measurement"""
    target = result_root_path / "logs" / "sched-order.txt"

    with open(target, "r") as f:
        sched_commands = f.readlines()
        return list(map(lambda s: s.replace("\n", ""), sched_commands))


def get_sched_name_from_sched_command(full_command: str) -> str:
    """Determines the scheduler program name of a given scheduler command"""
    if full_command == "EEVDF" or full_command == "CFS":
        return full_command

    cmd_parts = full_command.split(" ")
    sched_program_path = Path(cmd_parts[0])
    return sched_program_path.stem


def get_sched_cmd_idx(root: Path, sched_cmd: str) -> int:
    """Gets the index of a scheduler command within the scheduler command order file"""
    sched_cmds = get_sched_command_order(root)
    return sched_cmds.index(sched_cmd)


def get_sched_number(root: Path, sched_command: str) -> int:
    """Returns the number of a scheduling command

    A scheduler program can be used multiple times with different parameters.
    The measurement appends an increasing number to all log files to distinguish them.
    This function returns the used number for a given sched_command
    """
    used_sched_order = get_sched_command_order(root)
    sched_program_name = get_sched_name_from_sched_command(sched_command)
    used_sched_program_variations = list(
        filter(lambda cmd: sched_program_name in cmd, used_sched_order)
    )

    return used_sched_program_variations.index(sched_command)


def get_sched_log_name(root: Path, sched_cmd: str) -> str:
    sched_name = get_sched_name_from_sched_command(sched_cmd)
    sched_number = get_sched_number(root, sched_cmd)

    if sched_name == "EEVDF" or sched_name == "CFS":
        sched_number = ""

    return f"{sched_name}{sched_number}"
