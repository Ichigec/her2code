#!/bin/bash
# Wrapper for running x86-64 AAPT2 on ARM64 via QEMU
QEMU=/usr/bin/qemu-x86_64-static
ROOTFS=/полностью\ рабочее\ с\ openhands,\ openwebui/.local/ubuntu-amd64-root
AAPT2=$HOME/Android/Sdk/build-tools/34.0.0/aapt2

exec $QEMU -L "$ROOTFS" "$AAPT2" "$@"
