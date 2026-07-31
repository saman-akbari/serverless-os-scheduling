#!/bin/bash

if [[ ! -f "setup.sh" || ! -d "linux_scheds" ]]; then
	echo "ERROR: setup.sh must be executed from inside the open-lambda/ directory."
	exit 1
fi

# cli args
if [[ $# -ne 1 || ($# -eq 1 && $1 != "local" && $1 != "remote" && $1 != "remote-cfs") ]]; then
	echo "Wrong Usage"
	echo ""
	echo "Usage: $0 [exec-mode]"
	echo "  exec-mode: can be \"local\" or \"remote\""
	exit 1
fi

# parse mode
isLocalExec=0
if [[ $# -eq 1 && "$1" = "local" ]]; then
	isLocalExec=1
fi
isRemoteExec=0
if [[ $# -eq 1 && "$1" = "remote" ]]; then
	isRemoteExec=1
fi
isRemoteCFS=0
if [[ $# -eq 1 && "$1" = "remote-cfs" ]]; then
	isRemoteCFS=1
fi

# remove "Daemons using outdated libs" popup on remote-cfs machine
# interrupts otherwise script execution
# source: https://stackoverflow.com/questions/73397110/how-to-stop-ubuntu-pop-up-daemons-using-outdated-libraries-when-using-apt-to-i
if [[ isRemoteCFS -eq 1 ]]; then
	echo "\$nrconf{restart} = 'a';" >>/etc/needrestart/needrestart.conf
fi

# setup
sudo apt update
sudo apt upgrade -y

# install scx
if [[ isRemoteExec -eq 1 || (isLocalExec -eq 1 && (! -d "./scx")) ]]; then
	echo "Installing scx..."

	sudo apt install -y build-essential meson cmake clang llvm pkg-config libelf-dev rustup \
	    protobuf-compiler libseccomp-dev systemd-dev libzstd-dev
	rustup install 1.64
	rustup default 1.64

	git clone https://github.com/sched-ext/scx.git
	cd scx || exit 1
	git checkout 36048b96
	cd .. || exit 1
fi

# build sched_ext schedulers (not during remote-cfs)
if [[ $isRemoteCFS -eq 0 ]]; then
	cd scx || exit 1
	#rm -rf build
	#meson setup build
	meson compile -C build
	cargo build --release
	cd .. || exit 1
fi

# build OpenLambda
if [[ isRemoteExec -eq 1 || isRemoteCFS -eq 1 || (isLocalExec -eq 1 && (! -d "./open-lambda")) ]]; then
	echo "Installing open-lambda..."

	sudo apt install -y docker.io python3 zlib1g-dev llvm-dev libclang-dev build-essential python3 zlib1g-dev sysstat
	wget -q -O /tmp/go.tar.gz https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
	sudo tar -C /usr/local -xzf /tmp/go.tar.gz
	sudo ln -sf /usr/local/go/bin/go /usr/bin/go
	git clone https://github.com/open-lambda/open-lambda.git
	cd open-lambda || exit 1
	git checkout 3fe5547e # pin version

	# overwrites
	cp ../override/lambdaServer.go ./src/worker/event/lambdaServer.go      # log turnaround time of request ids
	cp ../override/stats.go ./src/common/stats.go                          # record startTime in Latency struct
	sed -i "s/1024/10240/g" ./src/worker/lambda/lambdaManager.go           # increase queue size

	# fixes make error on cfs machine
	if [[ isRemoteCFS -eq 1 ]]; then
		sed -i "s/build -o/build -buildvcs=false -o/g" ./Makefile
	fi

	sudo make ol imgs/ol-min
	cd .. || exit 1
fi

# build linux-scheds
cd ./linux_scheds || exit 1
clang -Wall -std=c11 -g -D_DEFAULT_SOURCE -o ./linux-scheds ./linux-scheds.c
cd .. || exit 1

# track always used cpu during measurement
sudo lscpu >lscpu.log
