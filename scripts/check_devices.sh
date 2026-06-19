#!/usr/bin/env bash
set -euo pipefail

printf 'ARIS optional hardware device inventory\n'
printf 'USB buses:\n'
lsusb || true
printf '\nSerial by-id:\n'
find /dev/serial/by-id -maxdepth 1 -type l -print 2>/dev/null || true
printf '\nVideo devices:\n'
find /dev -maxdepth 1 -name 'video*' -print 2>/dev/null || true
printf '\nCAN devices:\n'
find /dev -maxdepth 1 -name 'can*' -print 2>/dev/null || true
printf '\nThis command only inspects devices. Hardware mode remains opt-in.\n'
