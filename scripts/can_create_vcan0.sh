#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null 2>&1 || {
  printf 'ERROR: docker is required. Enter nix develop.\n' >&2
  exit 1
}

cat >&2 <<'MSG'
Creating vcan0 requires NET_ADMIN inside a helper container.
This is a separated hardware/network helper, not part of the default simulation command.
No sudo is used on the host.
MSG

docker run --rm --network host --cap-add NET_ADMIN ubuntu:24.04 bash -lc '
  set -euo pipefail
  apt-get update >/dev/null
  apt-get install -y --no-install-recommends iproute2 kmod >/dev/null
  modprobe vcan 2>/dev/null || true
  ip link show vcan0 >/dev/null 2>&1 || ip link add dev vcan0 type vcan
  ip link set up vcan0
  ip -details link show vcan0
'
