#!/bin/bash

# Asserts that measurement parameter is either local or remote
# Arguments:
#   $1: received execution mode of measurement
assertCorrectExecModeArg() {
	if [[ "$1" != "local" && "$1" != "remote" && "$1" != "remote-cfs" ]]; then
		echo "ERROR: Invalid execution mode argument in ${FUNCNAME[1]}"
		echo "ERROR: Expected: \"remote\" or \"local\", but got $1"
		exit 2
	fi
}

checkUsage() {
	if [[ "$#" -eq 0 || "$#" -gt 2 ]] ||
		[[ ("$1" != "local" && "$1" != "remote") ]]; then
		echo "Invalid Usage"
		echo ""
		echo "USAGE: $0 mode [path-to-plan]"
		echo "  mode:
    measurement mode, 
    possible values: \"local\" or \"remote\""
		echo "  path-to-plans:   
    skips plan generation phase if given and reuses given plans at path
    ONLY IN LOCAL MODE AVAILABLE"
		exit 1
	fi

	if [ "$#" -eq 1 ]; then
		return 0
	fi

	# validate plans path
	if [ ! -d "$2" ]; then
		echo "ERROR: Given plans-path doesn't exist or is not a directory"
		exit 1
	elif [ ! -f "$2/plan0.csv" ]; then
		echo "ERROR: Given plans-path doesn't contain plan0.csv"
		exit 1
	fi
}

# Provisions gcp infrastructure according to mode
# Arguments:
#   $1: exec mode
set_gcp_image() {
	mode="$1"
	if [[ "$mode" == "remote" ]]; then
		GCE_IMAGE="ubuntu-2504-plucky-amd64-v20250508"
	elif [[ "$mode" == "remote-cfs" ]]; then
		GCE_IMAGE="ubuntu-2204-jammy-v20220420"
	else
		echo "ERROR: $0 received unknown mode: $mode"
		exit 1
	fi
}

# Provisions gcp infrastructure according to mode
# Arguments:
#   $1: exec mode
#    if set to remote-cfs it uses older compute engine image to get a Linux kernel with version < 6.6
#   $2 output folder, if mode=remote-cfs: reuse plans
setup_gcp_infrastructure() {
	# validate function args
	assertCorrectArgNumber $# 2
	assertCorrectExecModeArg "$1"
	mode="$1"
	output_folder="$2"

	set_gcp_image "$mode"
	cd ./terraform || exit 1
	TF_VAR_OPEN_LAMBDA_IMAGE="$GCE_IMAGE" terraform init
	TF_VAR_OPEN_LAMBDA_IMAGE="$GCE_IMAGE" terraform plan
	TF_VAR_OPEN_LAMBDA_IMAGE="$GCE_IMAGE" terraform apply -auto-approve

	echo "Terraform apply completed with $?!"
	GCP_USER=$(terraform output -raw gcp_user)
	LOAD_INSTANCE_IP=$(terraform output -raw load_instance_public_ip)
	OL_INSTANCE_IP=$(terraform output -raw ol_instance_public_ip)
	GCP_PRIVATE_KEY_FILEPATH=$(terraform output -raw gcp_private_key_filepath)
	echo "env assignment completed!"

	if [ -z "$GCP_USER" ] || [ -z "$LOAD_INSTANCE_IP" ] ||
		[ -z "$OL_INSTANCE_IP" ] || [ -z "$GCP_PRIVATE_KEY_FILEPATH" ]; then
		echo "ERROR: encountered an empty terraform output variable"
		exit 1
	fi

	cd .. || exit 1
	echo "cd .. worked with $?!"

	# wait some time to ensure that both instances are ready
	# Background:
	# in some rare cases the load instances is not ready after tf
	# which leads to a failed rsync
	sleep 60

	# transfer local files to OL and load instance
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		--exclude="open-lambda" \
		--exclude="scx" \
		-r ./open-lambda/ "$GCP_USER@$OL_INSTANCE_IP:~"
	echo "Transfer to ol completed with $?!"

	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		--exclude=".env" \
		-r ./load-instance/ "$GCP_USER@$LOAD_INSTANCE_IP:~"
	echo "1. Transfer to load completed with $?!"

	# transfer previously generated plans to remote instance
	if [[ "$mode" == "remote-cfs" ]]; then
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			--exclude=".env" \
			-r "./$output_folder/plans/" "$GCP_USER@$LOAD_INSTANCE_IP:~/workload-generation/plans"
		echo "2. Transfer to load completed with $?!"
	fi
}

# Arguments:
#   $1: measurement mode, either "local", "remote" or "remote-cfs"
setup_ol_instance() {
	# validate function args
	assertCorrectArgNumber $# 1
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cd ./open-lambda || exit 1
		./setup.sh "$1"
		checkReturnValue $?
		cd .. || exit 1
		return 0
	fi

	# remote
	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$OL_INSTANCE_IP" \
		"bash ./setup.sh \"$1\""
	checkReturnValue $?
}

# Arguments:
#   $1: measurement mode, either "local" or "remote"
setup_load_instance() {
	assertCorrectArgNumber $# 1
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cd ./load-instance || exit 1
		./setup.sh
		checkReturnValue $?
		cd .. || exit 1
		return 0
	fi

	# remote
	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$LOAD_INSTANCE_IP" \
		"bash ./setup.sh"
	checkReturnValue $?
}

# Arguments
#  $1: measurement mode
#  $2: used sched_ext command
configure_ol_instance() {
	# validate function args
	assertCorrectArgNumber $# 2
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cd ./open-lambda || exit 1
		./configure-test.sh "$2"
		checkReturnValue $?
		cd .. || exit 1
		return 0
	fi

	# remote
	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$OL_INSTANCE_IP" \
		"./configure-test.sh '$2' || exit"
	checkReturnValue $?
}

# Arguments
#  $1: measurement mode
#  $2: path to directory containing the plans in usual format
reuse_plans() {
	assertCorrectArgNumber $# 2
	assertCorrectExecModeArg "$1"
	# $2 validation is at usage stage

	if [[ "$1" == "local" ]]; then
		local plans_target_dir="./load-instance/workload-generation"
		# validate target folder
		if [ -d "$plans_target_dir/plans" ]; then
			rm -rfd "$plans_target_dir/plans"
		fi

		if [ -d "$plans_target_dir/results" ]; then
			echo "ERROR: found results folder in $plans_target_dir"
			exit 1
		fi

		echo "INFO: Skipping plan generation..."
		cp -r "$2/." "$plans_target_dir/plans/"
		return
	fi

	# remote or remote-cfs
	local plans_target_dir="$HOME/workload-generation/plans"
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		--exclude=".env" \
		-r "$2" "$GCP_USER@$LOAD_INSTANCE_IP:$plans_target_dir"
	echo "Transfering plans to load-instance completed with status=$?!"
}

# Arguments
#  $1: measurement mode
#  $2: number of plans to generate
#  $3: sample size
#  $4: target duration in min
generate_plan() {
	assertCorrectArgNumber $# 4
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cd ./load-instance || exit 1
		./generate_plans.sh "$2" "$3" "$4"
		checkReturnValue $?
		cd .. || exit 1
		return 0
	fi

	# remote
	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$LOAD_INSTANCE_IP" \
		"bash ./generate_plans.sh \"$2\" \"$3\" \"$4\""
	checkReturnValue $?
}

# Arguments
#  $1 measurement mode
#  $2 used sched_ext command
#  $3 plan id to use
#  $4 scaling parameter
execute_load_test() {
	assertCorrectArgNumber $# 4
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		echo "INFO: Execute load tests for $(basename "$2")"
		cd ./load-instance || exit 1
		./execute_plans.sh "$3" "$4"
		checkReturnValue $?
		cd .. || exit 1
		return 0
	fi

	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$LOAD_INSTANCE_IP" \
		"bash -c \"./execute_plans.sh $3 $4\""
	checkReturnValue $?
}

# Arguments
#  $1 measurement mode
#  $2 used sched_ext command or EEVDF or CFS
#  $3 measurement output directory
#  $4 current plan id
#  $5 current run id
save_ol_logs() {
	# validate and parse args
	assertCorrectArgNumber $# 5
	assertCorrectExecModeArg "$1"
	local mode="$1"
	local full_sched_cmd="$2"
	local measurement_out_dir="$3"
	local plan_id="$4"
	local run_id="$5"

	# ensure log dirctory exists
	mkdir -p "$measurement_out_dir/logs"

	# determine correct target file names for sched_ext and OL logs
	local scx_target
	local ol_target
	local mpstat_target
	local system_ctxt_target
	if [[ "$full_sched_cmd" == "EEVDF" || "$full_sched_cmd" == "CFS" ]]; then
		scx_target="$measurement_out_dir/logs/plan${plan_id}_${full_sched_cmd}_run${run_id}_scx.logs"
		ol_target="$measurement_out_dir/logs/plan${plan_id}_${full_sched_cmd}_run${run_id}_ol.logs"
		mpstat_target="$measurement_out_dir/logs/plan${plan_id}_${full_sched_cmd}_run${run_id}_mpstat.logs"
		system_ctxt_target="$measurement_out_dir/logs/plan${plan_id}_${full_sched_cmd}_run${run_id}_system-ctxt.logs"
	else
		# fetch name of the sched_ext program
		local used_sched_program_name
		used_sched_program_name="$(echo "$full_sched_cmd" | awk '{print $1}' | xargs basename)"

		# same sched_ext program can be called with different params
		# use increasing index in filename to differentiate them
		i=0
		while [ -f "$measurement_out_dir/logs/plan${plan_id}_${used_sched_program_name}${i}_run${run_id}_scx.logs" ]; do
			((i++))
		done
		scx_target="$measurement_out_dir/logs/plan${plan_id}_${used_sched_program_name}${i}_run${run_id}_scx.logs"
		ol_target="$measurement_out_dir/logs/plan${plan_id}_${used_sched_program_name}${i}_run${run_id}_ol.logs"
		mpstat_target="$measurement_out_dir/logs/plan${plan_id}_${used_sched_program_name}${i}_run${run_id}_mpstat.logs"
		system_ctxt_target="$measurement_out_dir/logs/plan${plan_id}_${used_sched_program_name}${i}_run${run_id}_system-ctxt.logs"
	fi

	# store local logs in target files
	if [ "$mode" = "local" ]; then
		if [ "$full_sched_cmd" != "EEVDF" ]; then
			mv ./open-lambda/scx.log "$scx_target"
		fi
		mv ./open-lambda/mpstat.log "$mpstat_target"
		mv ./open-lambda/system-ctxt.logs "$system_ctxt_target"
		mv ./open-lambda/lscpu.log "$measurement_out_dir/logs/"
		cp "/tmp/ol/worker.out" "$ol_target"
		return 0
	fi

	# store remote logs in target files
	if [ "$full_sched_cmd" != "EEVDF" ]; then
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			-r "$GCP_USER@$OL_INSTANCE_IP:~/scx.log" \
			"$scx_target"
	fi
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		-r "$GCP_USER@$OL_INSTANCE_IP:~/mpstat.log" \
		"$mpstat_target"
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		-r "$GCP_USER@$OL_INSTANCE_IP:~/system-ctxt.logs" \
		"$system_ctxt_target"
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		-r "$GCP_USER@$OL_INSTANCE_IP:/tmp/ol/worker.out" \
		"$ol_target"

	if [[ "$mode" == "remote" ]]; then
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			-r "$GCP_USER@$OL_INSTANCE_IP:~/lscpu.log" \
			"$measurement_out_dir/logs/lscpu-EEVDF.log"
	elif [[ "$mode" == "remote-cfs" ]]; then
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			-r "$GCP_USER@$OL_INSTANCE_IP:~/lscpu.log" \
			"$measurement_out_dir/logs/lscpu-cfs.log"
	fi
}

# Arguments
#  $1 measurement mode
#  $2 used sched_ext command
reset_ol_instance() {
	assertCorrectArgNumber $# 2
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cd ./open-lambda || exit 1
		./cleanup.sh "$2"
		checkReturnValue $?
		cd ..
		return 0
	fi

	ssh -i "$GCP_PRIVATE_KEY_FILEPATH" -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null "$GCP_USER@$OL_INSTANCE_IP" \
		"bash  -c \"./cleanup.sh '$2'\""
	checkReturnValue $?
}

# Arguments
#  $1 measurement mode
#  $2 output folder to results to
save_results() {
	assertCorrectArgNumber $# 2
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		cp -r ./load-instance/workload-generation/results "$2"
		cp -r ./load-instance/workload-generation/samples "$2"
		cp -r ./load-instance/workload-generation/plans "$2"
		return 0
	fi

	# remote or remote-cfs
	rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
		-r "$GCP_USER@$LOAD_INSTANCE_IP:~/workload-generation/results/" \
		"$2/results"
	if [[ "$mode" == "remote" ]]; then
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			-r "$GCP_USER@$LOAD_INSTANCE_IP:~/workload-generation/samples" \
			"$2"
		rsync -e "ssh -i \"$GCP_PRIVATE_KEY_FILEPATH\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
			-r "$GCP_USER@$LOAD_INSTANCE_IP:~/workload-generation/plans" \
			"$2"
	fi
}

# Arguments
#  $1 measurement mode
cleanup() {
	assertCorrectArgNumber $# 1
	assertCorrectExecModeArg "$1"

	if [ "$1" = "local" ]; then
		#rm ./load-instance/data/AzureFunctionsInvocationTraceForTwoWeeksJan2021.txt
		#rm -rfd ./load-instance/.env
		return 0
	fi

	# remote
	set_gcp_image "$1"
	cd terraform || exit 1
	TF_VAR_OPEN_LAMBDA_IMAGE="$GCE_IMAGE" terraform destroy -auto-approve
	checkReturnValue $?
	cd ..
}

# Arguments
#  $1 outfolder on local machine
#  scheduler are passed through global SCHED variable
save_sched_commands() {
	assertCorrectArgNumber $# 1

	mkdir -p "$1"/logs
	output_file="$1/logs/sched-order.txt"
	touch "$output_file"
        for SCHED in "${SCHEDS[@]}"; do
		echo "$SCHED" >>"$output_file"

	done
}
