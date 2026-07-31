#!/bin/bash
# parse cli arguments
if [ "$#" -ne 1 ]; then
	echo "ERROR: missing scheduler argument"
	echo "Usage: $0 [sched_ext-scheduler-path]"
	exit 1
fi

# setup ol worker
cd ./open-lambda || exit 1

# use minimal Ol path length
# to prevent buffer overflow errors
# resulted by sock paths with length > 108
DEFAULT_OL_PATH="/tmp/ol"

if sudo test -f ./default-ol/worker/worker.pid ||
	sudo test -f "$DEFAULT_OL_PATH/worker/worker.pid"; then
	echo "ERROR: Found a running ol instance"
	exit 1
fi

sudo rm -rfd "$DEFAULT_OL_PATH"
sudo ./ol worker init -i ol-min --path "$DEFAULT_OL_PATH"

sudo chmod 777 "$DEFAULT_OL_PATH"
sudo chmod 777 $DEFAULT_OL_PATH/registry/
sudo cp -R ../registry/* "$DEFAULT_OL_PATH/registry/"
sudo chmod -R 777 "$DEFAULT_OL_PATH/registry"

sudo sed -i 's/localhost/0.0.0.0/' "$DEFAULT_OL_PATH/config.json"
sudo sed -i 's/"max_runtime_default": 30,/"max_runtime_default": 600,/g' "$DEFAULT_OL_PATH/config.json"
#sudo sed -i 's/"procs": 10,/"procs": 64,/g' "$DEFAULT_OL_PATH/config.json"
sudo sed -i 's/"mem_mb": 50,/"mem_mb": 100,/g' "$DEFAULT_OL_PATH/config.json"
sudo sed -i 's/"latency": false/"latency": true/' "$DEFAULT_OL_PATH/config.json" # track latencies
sudo sed -i 's/"tree"/""/' "$DEFAULT_OL_PATH/config.json"

#sudo strace -e fork,vfork,clone,execve -o strace.log -f ./ol worker up --path "$DEFAULT_OL_PATH"
nohup sudo ./ol worker up -d -p "$DEFAULT_OL_PATH" -i ol-min >/tmp/ol/worker.out 2>&1 &
sleep 5

if [ -z "$(sudo ./ol worker status --path "$DEFAULT_OL_PATH" 2>/dev/null | grep ready)" ]; then
	echo "ERROR: Couldn't reach worker after starting it"
	exit 1
fi

echo 0-$(($(nproc) - 1)) | sudo tee /sys/fs/cgroup/ol-sandboxes/cpuset.cpus || exit 1

cd .. || exit 1

# track cpu utilization
nohup mpstat -P 0,1,2,3,4,5,6,7 1 >"./mpstat.log" 2>&1 &

# track system-wide context switches
nohup sudo ./track-system-ctxt-switches.sh >./system-ctxt.logs 2>&1 &


# enable sched_ext
sched_state_file=/sys/kernel/sched_ext_state
if [[ -e "$sched_state_file" && "$(cat "$sched_state_file")" != "disabled" ]]; then
	echo "ERROR: Sched_ext was enabled before enabling it"
	exit 1
fi

if [[ "$1" = "EEVDF" || "$1" = "CFS" ]]; then
	# use default os scheduler
	exit 0
fi

nohup bash -c "sudo $1" >./scx.log 2>&1 &

if [[ "$(echo "$1" | grep linux_scheds | wc -l)" -eq 1 ]]; then
	# use default os scheduling policy controlled through c program
	exit 0
fi

timeout=120
elapsed=0
while [ "$(sudo cat /sys/kernel/sched_ext/state)" != "enabled" ]; do
    sleep 1
    elapsed=$((elapsed+1))
    if [ "$elapsed" -ge "$timeout" ]; then
        echo "Error: Sched_ext is not enabled after $timeout seconds"
        exit 1
    fi
done
echo "Sched_ext enabled in $elapsed seconds!"
