#!/bin/bash
while true; do
	curr_time="$(date --rfc-3339 s)"
	ctxt="$(cat /proc/stat | grep ctxt | awk '{ print $2 }')"
	echo "$curr_time $ctxt"
	sleep 1
done
