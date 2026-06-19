#!/usr/bin/env bash
set -euo pipefail

aris_repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "${script_dir}/.." && pwd
}

aris_load_env() {
  export ARIS_HOME="${ARIS_HOME:-${HOME}/aris}"
  export ARIS_WS="${ARIS_WS:-$(aris_repo_root)}"
  export ARIS_DATA="${ARIS_DATA:-${ARIS_HOME}/data}"
  export ARIS_LOGS="${ARIS_LOGS:-${ARIS_HOME}/logs}"
  export ARIS_MODELS="${ARIS_MODELS:-${ARIS_HOME}/models}"
  export HF_HOME="${HF_HOME:-${ARIS_MODELS}/hf}"
  export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-${ARIS_MODELS}/hf}"
  export TORCH_HOME="${TORCH_HOME:-${ARIS_MODELS}/torch}"
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
  export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
  export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
  export ARIS_ENABLE_REAL_ACTUATION="${ARIS_ENABLE_REAL_ACTUATION:-0}"
  export ARIS_UID="${ARIS_UID:-$(id -u)}"
  export ARIS_GID="${ARIS_GID:-$(id -g)}"
  export ARIS_XAUTHORITY="${ARIS_XAUTHORITY:-}"

  mkdir -p "$ARIS_DATA" "$ARIS_LOGS" "$ARIS_MODELS" "$HF_HOME" "$TORCH_HOME"

  if [[ -z "$ARIS_XAUTHORITY" ]]; then
    if [[ -n "${XAUTHORITY:-}" && -r "${XAUTHORITY:-}" ]]; then
      export ARIS_XAUTHORITY="$XAUTHORITY"
    elif [[ -r "${HOME}/.Xauthority" ]]; then
      export ARIS_XAUTHORITY="${HOME}/.Xauthority"
    else
      export ARIS_XAUTHORITY="${ARIS_HOME}/.empty-Xauthority"
      : >"$ARIS_XAUTHORITY"
    fi
  fi
}

aris_die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

aris_need_cmd() {
  command -v "$1" >/dev/null 2>&1 || aris_die "Missing command '$1'. Enter 'nix develop' from the repository root."
}

aris_check_docker_access() {
  aris_need_cmd docker
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  printf 'ERROR: Docker is not usable by this user.\n' >&2
  printf '  user: %s\n' "$(id -un)" >&2
  printf '  groups: %s\n' "$(id -nG)" >&2
  if [[ -S /var/run/docker.sock ]]; then
    printf '  docker socket: %s\n' "$(ls -l /var/run/docker.sock)" >&2
  else
    printf '  docker socket: /var/run/docker.sock not found\n' >&2
  fi
  printf 'Ask the machine owner to make Docker usable by this login session, usually by adding the user to the docker group and starting a fresh login session. Do not use sudo in this repo.\n' >&2
  exit 1
}

aris_compose() {
  aris_check_docker_access
  docker compose -f "$(aris_repo_root)/docker/compose.yaml" "$@"
}

aris_check_gui_env() {
  [[ -n "${DISPLAY:-}" ]] || aris_die "DISPLAY is empty. Start an X11 session or set DISPLAY before launching GUI tools."

  if [[ "${ARIS_SKIP_X11_CHECK:-0}" == "1" ]]; then
    return 0
  fi

  if [[ -n "${XAUTHORITY:-}" && ! -r "${XAUTHORITY:-}" && ! -r "${HOME}/.Xauthority" ]]; then
    aris_die "XAUTHORITY points to '${XAUTHORITY}', but this user cannot read it. Run from a terminal inside your desktop login, export a readable XAUTHORITY, or set ARIS_SKIP_X11_CHECK=1 if X access is granted another way."
  fi

  if command -v xhost >/dev/null 2>&1 && ! xhost >/dev/null 2>&1; then
    aris_die "This shell cannot open DISPLAY='${DISPLAY}'. Fix local X11 authorization first, then rerun the GUI command."
  fi
}

aris_check_ngc_image() {
  local env_file
  env_file="$(aris_repo_root)/.env"
  if [[ ! -f "$env_file" ]]; then
    aris_die "Missing .env. Run 'cp .env.example .env' and set NGC_PYTORCH_IMAGE to a real arm64 DGX Spark compatible tag."
  fi
  if grep -q '<choose-current-arm64-dgx-spark-compatible-tag>' "$env_file"; then
    aris_die "NGC_PYTORCH_IMAGE still contains the placeholder tag. Edit .env before building the AI container."
  fi
}

aris_ngc_image_configured() {
  local env_file
  env_file="$(aris_repo_root)/.env"
  [[ -f "$env_file" ]] || return 1
  ! grep -q '<choose-current-arm64-dgx-spark-compatible-tag>' "$env_file"
}
