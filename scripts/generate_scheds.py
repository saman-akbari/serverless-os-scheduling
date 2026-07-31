import copy
import json
import math
import os
import random
from datetime import datetime

RANDOM_SEED = math.floor(datetime.now().timestamp())
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

CONFIGS_FOLDER = os.path.join(ROOT_DIR, "open-lambda", "scx_layered_configs")
TEMPLATE_PATH = os.path.join(CONFIGS_FOLDER, "template", "scx_layered-config.json")
random.seed(RANDOM_SEED)

C_SCHEDS_PATH = "./scx/build/scheds/c"
C_SCHEDS = {
    "scx_central": {
        "samples": 5,
        "withDefault": True,
        "parameterRanges": {
            "-s": {
                "type": "randomInt",
                "start": 1000,
                "stop": 50001,
            }
        },
    },
    "scx_simple": {},
    "scx_simple -f": {},
    "scx_nest": {},
    "scx_pair": {},
    "scx_flatcg": {},
    "scx_flatcg -f": {},
    "scx_prev": {},
}

RUST_SCHEDS_PATH = "./scx/target/release"
RUST_SCHEDS = {
    "scx_lavd": {},
    "scx_lavd --performance": {},
    "scx_lavd --no-preemption --no-core-compaction --no-freq-scaling": {
        "samples": 5,
        "withDefault": True,
        "withConstraints": True,
        "parameterRanges": {
            "--slice-min-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--slice-max-us": {
                "lowerBoundedBy": "--slice-min-us",
                "type": "randomInt",
                "stop": 100001,
            },
        },
    },
    "scx_mitosis": {
        "samples": 5,
        "withDefault": True,
        "parameterRanges": {
            "--reconfiguration-interval-s": {
                "type": "randomInt",
                "start": 1,
                "stop": 11,
            },
            "--rebalance-cpus-interval-s": {
                "type": "randomInt",
                "start": 1,
                "stop": 11,
            },
        },
    },
    "scx_rustland": {
        "samples": 5,
        "withDefault": True,
        "parameterRanges": {
            "--slice-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--slice-us-min": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
        },
    },
    "scx_bpfland": {
        "samples": 5,
        "withDefault": True,
        "parameterRanges": {
            "--slice-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--slice-us-lag": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
        },
    },
    "scx_rusty --no-load-balance": {
        "samples": 10,
        "withDefault": True,
        "gridParamRanges": {"--fifo-sched": {"type": "toggle"}},
        "parameterRanges": {
            "--slice-us-underutil": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--slice-us-overutil": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
        },
    },
    "scx_tickless": {
        "samples": 10,
        "withDefault": True,
        "gridParamRanges": {"--primary-domain 2": {"type": "toggle"}},
        "parameterRanges": {
            "--slice-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--frequency": {
                "type": "randomInt",
                "start": 250,
                "stop": 1001,
            },
        },
    },
    "scx_cosmos": {
        "samples": 5,
        "withDefault": True,
        "parameterRanges": {
            "--cpu-busy-thresh": {
                "type": "randomInt",
                "start": 1,
                "stop": 101,
            },
            "--slice-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
            "--slice-lag-us": {
                "type": "randomInt",
                "start": 1000,
                "stop": 100001,
            },
        },
    },
    "scx_layered": {},
}

LINUX_SCHEDS_PATH = "./linux_scheds"
LINUX_SCHEDS = {
    "linux-scheds SCHED_FIFO": {},
    "linux-scheds SCHED_RR 1": {},
    "linux-scheds SCHED_RR 5": {},
    "linux-scheds SCHED_RR 10": {},
    "linux-scheds SCHED_RR 20": {},
    "linux-scheds SCHED_RR 30": {},
    "linux-scheds SCHED_RR 40": {},
    "linux-scheds SCHED_RR 50": {},
    "linux-scheds SCHED_RR 60": {},
    "linux-scheds SCHED_RR 70": {},
    "linux-scheds SCHED_RR 80": {},
    "linux-scheds SCHED_RR 90": {},
    "linux-scheds SCHED_RR 100": {},
}


def append_parameter(
        current_cmd: str, param_name: str, param_value: str, sampling_info: dict
) -> str:
    if (
            "withoutParamName" in sampling_info
            and sampling_info["withoutParamName"] is not None
            and sampling_info["withoutParamName"]
    ):
        return f"{current_cmd} {param_value}"
    return f"{current_cmd} {param_name} {param_value}"


def get_commands(full_sched_cmd: str, sampling_info: dict[str, any]) -> list[str]:
    result = []

    if "samples" not in sampling_info:
        result.append(full_sched_cmd)
        return result

    num_samples = sampling_info["samples"]

    if "samples" not in sampling_info:
        result.append(full_sched_cmd)
        return result

    if "withDefault" in sampling_info and sampling_info["withDefault"]:
        result.insert(0, full_sched_cmd)

    num_samples = sampling_info["samples"]

    combinations = []
    if "gridParamRanges" in sampling_info:
        for grid_param, grid_param_info in sampling_info["gridParamRanges"].items():
            if grid_param_info["type"] == "toggle":
                if len(combinations) == 0:
                    combinations.extend(["", grid_param])
                    continue

                new_combinations = []
                for combination in combinations:
                    new_combinations.extend(
                        [combination, f"{combination} {grid_param}"]
                    )
                combinations.extend(new_combinations)

    params = sampling_info["parameterRanges"]
    if "withConstraints" in sampling_info and sampling_info["withDefault"]:
        dependent_params = [tpl for tpl in params.items() if "lowerBoundedBy" in tpl[1]]
        independent_params = [
            tpl for tpl in params.items() if "lowerBoundedBy" not in tpl[1]
        ]
    else:
        dependent_params = []
        independent_params = [tpl for tpl in params.items()]

    actual_num_samples = (
        math.floor(num_samples / len(combinations))
        if len(combinations) != 0
        else num_samples
    )
    for index in range(actual_num_samples):
        curr_cmd = full_sched_cmd

        current_params = {}
        for param_name, param_sampling_info in independent_params:
            sampling_type = param_sampling_info["type"]

            if sampling_type == "randomInt":
                start = param_sampling_info["start"]
                stop = param_sampling_info["stop"]
                param_value = random.randrange(start, stop)
                current_params[param_name] = param_value
                curr_cmd = append_parameter(
                    curr_cmd, param_name, param_value, param_sampling_info
                )

            if sampling_type == "grid":
                param_value = param_sampling_info["values"][index]
                current_params[param_name] = param_value
                curr_cmd = append_parameter(
                    curr_cmd, param_name, param_value, param_sampling_info
                )

        for param_name, param_sampling_info in dependent_params:
            sampling_type = param_sampling_info["type"]

            if "lowerBoundedBy" in param_sampling_info and sampling_type == "randomInt":
                lower_bound_param_name = param_sampling_info["lowerBoundedBy"]
                start = current_params[lower_bound_param_name]
                stop = param_sampling_info["stop"]
                param_value = random.randrange(start, stop)
                # current_params[param_name] = param_value
                curr_cmd = append_parameter(
                    curr_cmd, param_name, param_value, param_sampling_info
                )

        result.append(curr_cmd)

    new_results = []
    for r in result:
        for combi in combinations:
            if combi != "":
                parts = r.split(" ")
                new_results.append(f"{parts[0]} {combi} {' '.join(parts[1:])}")
    result.extend(new_results)

    return result


def get_scx_layered_commands(sched_path: str, _: dict[str, any]):
    # generate samples
    configs = []
    num_samples = 10
    for index in range(num_samples):
        curr_configs = []
        config_base = {
            "ol-layer": {
                "weight": random.randrange(100, 401),
                "slice_us": random.randrange(1000, 100001),
            },
            "rest-layer": {
                "cpus_range": [0, random.randrange(4, 9)],
                "slice_us": random.randrange(1000, 20001),
            },
        }
        for fifo in [False, True]:
            for preempt in [False, True]:
                c = copy.deepcopy(config_base)
                print(fifo, preempt)
                c["ol-layer"]["fifo"] = fifo
                c["ol-layer"]["preempt"] = preempt
                curr_configs.append(c)
        configs.extend(curr_configs)

    # load template config
    template = get_scx_layered_config_template()

    config_paths = []
    for index, config in enumerate(configs):
        result_config = copy.deepcopy(template)
        target_filename = f"config{index}.json"

        assert (
                isinstance(template, list) and len(template) == 2
        ), "Received template in unexpected format"
        ol_layer = result_config[0]["kind"]["Grouped"]
        rest_layer = result_config[1]["kind"]["Grouped"]

        ol_layer = ol_layer | config["ol-layer"]
        rest_layer = rest_layer | config["rest-layer"]

        result_config[0]["kind"]["Grouped"] = ol_layer
        result_config[1]["kind"]["Grouped"] = rest_layer
        dump_scx_layered_config(target_filename, result_config)
        config_paths.append(f"./scx_layered_configs/{target_filename}")

    cmds = list(map(lambda path: f"{sched_path} file:{path}", config_paths))
    return cmds


def get_scx_layered_config_template():
    with open(TEMPLATE_PATH, "r") as f:
        data = f.read()
        assert len(data) != 0
        return json.loads(data)


def dump_scx_layered_config(target_filename: str, template):
    target_filepath = os.path.join(CONFIGS_FOLDER, target_filename)
    with open(target_filepath, "w") as f:
        s = json.dumps(template, indent=2)
        f.write(s)


def generate_sched_commands(sched_path: str, hpo_info: dict[str, any]) -> list[str]:
    result = []

    for cmd in hpo_info.keys():
        cmd_path = sched_path + "/" + cmd

        sampling_info = hpo_info[cmd]

        if cmd == "scx_layered":
            cmds = get_scx_layered_commands(cmd_path, sampling_info)
        else:
            cmds = get_commands(cmd_path, sampling_info)

        result.extend(cmds)
    return result


def save_sched_cmds(scheds: list[str], target_file: str = os.path.join(SCRIPT_DIR, "scheds.sh")):
    start_lines = [
        "#!/bin/bash\n",
        f"# used random seed was: {RANDOM_SEED}\n",
        "\n",
        "SCHEDS=(\n",
    ]
    end_lines = [")"]

    with open(target_file, "w") as f:
        f.writelines(start_lines)
        f.writelines(map(lambda cmd: f'\t"{cmd}"\n', scheds))
        f.writelines(end_lines)


if __name__ == "__main__":
    linux_scheds = generate_sched_commands(LINUX_SCHEDS_PATH, LINUX_SCHEDS)
    c_scheds = generate_sched_commands(C_SCHEDS_PATH, C_SCHEDS)
    rust_scheds = generate_sched_commands(RUST_SCHEDS_PATH, RUST_SCHEDS)
    all_scheds = ["EEVDF"] + c_scheds + rust_scheds + linux_scheds

    save_sched_cmds(all_scheds)

    # +1 due to cfs
    for rs in rust_scheds:
        print(rs)
    print(f"Total scheduler versions: {len(all_scheds) + 1}")
    print(f"This will take with 5min plans roughly {len(all_scheds) * 5 / 60:.2f}h")
