#!/bin/bash
# parse arguments
DEFAULT_OL_PATH="/tmp/ol"

# Arguments
# $1 the command name
stop_process() {
	sudo pkill -f "$1" 2>/dev/null || true
	echo "Successfully stopped $1 process"
	return 0
}

if [ "$#" -ne 1 ]; then
	echo "ERROR: missing scheduler argument"
	echo "Usage: $0 [sched_ext-scheduler-path]"
	exit 1
fi

# reset openlambda
cd open-lambda || exit 1
sudo ./ol worker down --path "$DEFAULT_OL_PATH"

if [[ $? -ne 0 ]]; then
	echo "Failed to gracefully shut down worker. Starting manual cleanup"
	sudo pkill -9 -f './ol worker up'
	sudo pkill -9 'python3'

	sudo rm -rfd /tmp/ol/
	sudo find /sys/fs/cgroup/ol-sandboxes/ -maxdepth 1 -type d -name "cg-*" \
		-exec rmdir {} + 2>/dev/null
	sudo rmdir /sys/fs/cgroup/ol-sandboxes/
fi

if [ ! -z "$(sudo ./ol worker status 2>/dev/null | grep ready)" ]; then
	echo "ERROR: Failed to stop worker"
	exit 1
fi

sudo rm -rfd "$DEFAULT_OL_PATH"
cd .. || exit 1

# stop logging processes
stop_process "mpstat"
stop_process "track-system-ctxt-switches.sh"

# stop scheduler
if [[ "$1" == "EEVDF" || "$1" == "CFS" ]]; then
	# nothing to stop
	exit
fi

stop_process "sudo $1"
sleep 10

isLinuxPolicy="$(echo "$1" | grep linux_scheds | wc -l)"
if [[ "$isLinuxPolicy" -eq 0 && "$(cat /sys/kernel/sched_ext/state)" != "disabled" ]]; then
	echo "ERROR: Failed to stop sched_ext"
	exit 1
fi
echo "Successfully stopped sched_ext scheduler: $1"
