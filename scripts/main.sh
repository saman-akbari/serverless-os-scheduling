#!/bin/bash

# imports
source ./scripts/common.sh
source ./scripts/measurement.sh

# Arguments
#  $1 execution mode
#  $2 output folder to store results
#  $3 plans path to reusue existing plans (optional)
execute_measurement() {
	# cli parsing
	local mode=$1
	local output_folder=$2
	local plans_path=$3

	if [[ "$mode" == "remote" || "$mode" == "remote-cfs" ]]; then
		setup_gcp_infrastructure "$mode" "$output_folder"
	fi

	setup_ol_instance "$mode"
	setup_load_instance "$mode"

	# reuse or generate plans
	local num_plans
	if [[ -n "$plans_path" && $mode == "local" ]]; then
		# reuse plans at given path
		echo "INFO: Reusing tests in mode=$mode"
		reuse_plans "$mode" "$plans_path"
		num_plans="$(find "$plans_path" -maxdepth 1 -name "plan*.csv" 2>/dev/null | grep -c "")"
	elif [[ -n "$plans_path" && ("$mode" == "remote" || "$mode" == "remote-cfs") ]]; then
		# reuse plans with remote instance
		echo "INFO: Reusing tests in mode=$mode"
		reuse_plans "$mode" "$plans_path"
		num_plans="$(find "$plans_path" -maxdepth 1 -name "plan*.csv" 2>/dev/null | grep -c "")"
	else
		# generate random plan at each measurement
		num_plans=1
		sample_size=600
		duration=5 # min
		configure_ol_instance "$mode" "EEVDF"
		generate_plan "$mode" "$num_plans" "$sample_size" "$duration"
		reset_ol_instance "$mode" "EEVDF"
	fi

	echo "INFO: Running tests..."
	# run tests
	local scaling=1.0 # fixed value
	local total_runs=1
	if [[ -e "./scripts/scheds.sh" ]]; then
		source ./scripts/scheds.sh
	else
		SCHEDS=(
			"EEVDF"
			"./scx/build/scheds/c/scx_simple"
		)
	fi

	if [[ "$mode" == "remote-cfs" ]]; then
		SCHEDS=(
			"CFS"
		)
	fi

	save_sched_commands "$output_folder"

	for SCHED in "${SCHEDS[@]}"; do
		for ((plan_id = 0; plan_id < num_plans; plan_id++)); do
			for ((run_id = 0; run_id < total_runs; run_id++)); do
				configure_ol_instance "$mode" "$SCHED"
				execute_load_test "$mode" "$SCHED" "$plan_id" "$scaling"
				if [ "$mode" = "local" ]; then
					sudo pkill -f track-system-ctxt-switches.sh 2>/dev/null || true
					sudo pkill -f mpstat 2>/dev/null || true
					sleep 0.5
				fi
				save_ol_logs "$mode" "$SCHED" "$output_folder" "$plan_id" "$run_id"
				reset_ol_instance "$mode" "$SCHED"
				save_results "$mode" "$output_folder"
			done
		done
	done

	# cleanup
	cleanup "$mode"
}

# main entrypoint
main() {
	# cli parsing
	checkUsage "$@"
	local mode=$1
	local plans_path=$2

	# create output folder
	local output_folder
	output_folder="./results/$(date -Iseconds)"
	mkdir -p "$output_folder"

	if [[ "$mode" == "local" ]]; then
		# execute measurement locally
		execute_measurement "$mode" "$output_folder" "$plans_path"
	else
		# execute measurement remotely with EEVDF
		execute_measurement "$mode" "$output_folder" "$plans_path"
		# execute remotely with only CFS and previously generated plans
		execute_measurement "remote-cfs" "$output_folder" "$output_folder/plans/"
	fi
}

# execute main only when directly calling main.py
# prevents executing of main when beeing sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	main "$@"
fi
