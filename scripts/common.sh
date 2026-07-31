#!/bin/bash

# Asserts that actual number of arguments equals expected amount
# Arguments:
#   $1: actual number of args
#   $2: expected number of args
assertCorrectArgNumber() {
	if [[ "$1" -ne "$2" ]]; then
		echo "ERROR: Invalid number of arguments in ${FUNCNAME[1]}"
		echo "ERROR: Expected $2 arg(s), but got $1"
		exit 1
	fi
}

# Checks if return value is equal 0, exists otherwise with returned error code
# Arguments:
#   $1: received return value
checkReturnValue() {
	if [ "$1" -ne 0 ]; then
		echo "ERROR: ${FUNCNAME[1]} received error code $1"
		exit "$1"
	fi
}
