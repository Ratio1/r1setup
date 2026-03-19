#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Run the repo r1setup script against a local dev collection workspace.

What this does:
- uses the r1setup script from this repo checkout
- builds a dev collection workspace from the local mnl_factory sources
- keeps runtime state under an isolated dev HOME
- optionally links the real ~/.ssh into that dev HOME for real-machine testing
- lets you choose which r1setup config store to use

Environment overrides:
- R1SETUP_DEV_HOME: custom dev HOME path
- R1SETUP_DEV_PYTHON: custom Python interpreter
- R1SETUP_LINK_REAL_SSH: set to 0 to avoid linking ~/.ssh
- R1SETUP_CONFIG_SOURCE: one of:
  - dev
  - real
  - /absolute/path/to/r1_setup
- R1SETUP_SKIP_AUTO_UPDATE: set to 0 to restore startup auto-update checks
- R1SETUP_NO_CLEAR: set to 0 to restore screen clearing behavior

Options:
- --reset    Remove the dev HOME before preparing the workspace
- --use-real-configs
- --config-source <dev|real|/absolute/path/to/r1_setup>
- -h, --help Show this help message

All remaining arguments are passed through to r1setup.
EOF
}

RESET_DEV_HOME=0
CONFIG_SOURCE=""
PASSTHROUGH_ARGS=()

while (($#)); do
  case "$1" in
    --reset)
      RESET_DEV_HOME=1
      shift
      ;;
    --use-real-configs)
      CONFIG_SOURCE="real"
      shift
      ;;
    --config-source)
      if (($# < 2)); then
        echo "--config-source requires a value" >&2
        exit 1
      fi
      CONFIG_SOURCE="$2"
      shift 2
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    --)
      shift
      PASSTHROUGH_ARGS+=("$@")
      break
      ;;
    *)
      PASSTHROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required for this helper script." >&2
  echo "Install rsync and run the script again." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_COLLECTION="$REPO_ROOT/mnl_factory"
REPO_R1SETUP="$REPO_COLLECTION/scripts/r1setup"

if [[ ! -f "$REPO_R1SETUP" ]]; then
  echo "Could not find repo r1setup at: $REPO_R1SETUP" >&2
  exit 1
fi

REAL_HOME="${HOME:?HOME must be set}"
DEV_HOME="${R1SETUP_DEV_HOME:-$REAL_HOME/.ratio1/dev_local_r1setup_home}"
DEV_RATIO1_BASE="$DEV_HOME/.ratio1"
DEV_ANSIBLE_DIR="$DEV_RATIO1_BASE/ansible_config"
DEV_COLLECTION_PARENT="$DEV_ANSIBLE_DIR/collections/ansible_collections/ratio1"
DEV_COLLECTION="$DEV_COLLECTION_PARENT/multi_node_launcher"
DEV_TMP="$DEV_ANSIBLE_DIR/tmp"
DEV_R1_SETUP_DIR="$DEV_RATIO1_BASE/r1_setup"
DEV_ANSIBLE_CFG="$DEV_ANSIBLE_DIR/ansible.cfg"
REAL_R1_SETUP_DIR="$REAL_HOME/.ratio1/r1_setup"

CONFIG_SOURCE="${CONFIG_SOURCE:-${R1SETUP_CONFIG_SOURCE:-dev}}"

if [[ "$RESET_DEV_HOME" -eq 1 ]]; then
  rm -rf "$DEV_HOME"
fi

mkdir -p "$DEV_COLLECTION_PARENT" "$DEV_TMP" "$DEV_R1_SETUP_DIR"

if [[ "${R1SETUP_LINK_REAL_SSH:-1}" != "0" && ! -e "$DEV_HOME/.ssh" && -d "$REAL_HOME/.ssh" ]]; then
  ln -s "$REAL_HOME/.ssh" "$DEV_HOME/.ssh"
fi

CONFIG_SOURCE_DIR=""
case "$CONFIG_SOURCE" in
  dev)
    CONFIG_SOURCE_DIR="$DEV_R1_SETUP_DIR"
    mkdir -p "$DEV_R1_SETUP_DIR/configs"
    ;;
  real)
    CONFIG_SOURCE_DIR="$REAL_R1_SETUP_DIR"
    ;;
  /*)
    CONFIG_SOURCE_DIR="$CONFIG_SOURCE"
    ;;
  *)
    echo "Unsupported config source: $CONFIG_SOURCE" >&2
    echo "Use dev, real, or an absolute path to an r1_setup directory." >&2
    exit 1
    ;;
esac

if [[ "$CONFIG_SOURCE" != "dev" ]]; then
  if [[ ! -d "$CONFIG_SOURCE_DIR" ]]; then
    echo "Config source directory does not exist: $CONFIG_SOURCE_DIR" >&2
    exit 1
  fi
  if [[ ! -d "$CONFIG_SOURCE_DIR/configs" ]]; then
    echo "Config source is missing configs/: $CONFIG_SOURCE_DIR" >&2
    exit 1
  fi

  rm -rf "$DEV_R1_SETUP_DIR/configs"
  ln -s "$CONFIG_SOURCE_DIR/configs" "$DEV_R1_SETUP_DIR/configs"

  if [[ -e "$DEV_R1_SETUP_DIR/active_config.json" || -L "$DEV_R1_SETUP_DIR/active_config.json" ]]; then
    rm -f "$DEV_R1_SETUP_DIR/active_config.json"
  fi
  if [[ -e "$CONFIG_SOURCE_DIR/active_config.json" ]]; then
    ln -s "$CONFIG_SOURCE_DIR/active_config.json" "$DEV_R1_SETUP_DIR/active_config.json"
  fi
fi

mkdir -p "$DEV_COLLECTION"

rsync -a --delete \
  --exclude '.ansible' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude 'tmp' \
  --exclude 'hosts.yml' \
  --exclude 'group_vars/variables.yml' \
  --exclude 'group_vars/vault.yml' \
  "$REPO_COLLECTION/" "$DEV_COLLECTION/"

mkdir -p "$DEV_COLLECTION/group_vars"

if [[ ! -f "$DEV_COLLECTION/group_vars/variables.yml" ]]; then
  cp "$REPO_COLLECTION/group_vars/variables.yml" "$DEV_COLLECTION/group_vars/variables.yml"
fi

if [[ ! -f "$DEV_COLLECTION/group_vars/vault.yml" ]]; then
  cat > "$DEV_COLLECTION/group_vars/vault.yml" <<'EOF'
---
# Local dev placeholder. Add real secret values here only if your test workflow needs them.
EOF
fi

cat > "$DEV_ANSIBLE_CFG" <<EOF
[defaults]
inventory = $DEV_COLLECTION/hosts.yml
host_key_checking = False
hash_behaviour = merge
local_tmp = $DEV_TMP
retry_files_enabled = False
collections_paths = $DEV_ANSIBLE_DIR/collections

[privilege_escalation]
become = True
become_method = sudo
become_ask_pass = False
EOF

PYTHON_BIN="${R1SETUP_DEV_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$REAL_HOME/.ratio1/r1_setup/.r1_venv/bin/python3" ]]; then
    PYTHON_BIN="$REAL_HOME/.ratio1/r1_setup/.r1_venv/bin/python3"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

echo "Repo root           : $REPO_ROOT"
echo "Repo r1setup        : $REPO_R1SETUP"
echo "Dev HOME            : $DEV_HOME"
echo "Dev collection      : $DEV_COLLECTION"
echo "Config source       : $CONFIG_SOURCE_DIR"
echo "Python              : $PYTHON_BIN"
echo "Skip auto-update    : ${R1SETUP_SKIP_AUTO_UPDATE:-1}"
echo "No-clear mode       : ${R1SETUP_NO_CLEAR:-1}"
echo
echo "This uses an isolated dev HOME and a workspace synced from the local repo."
if [[ "$CONFIG_SOURCE" == "dev" ]]; then
  echo "Your regular installed r1setup state under $REAL_HOME/.ratio1 is not modified."
else
  echo "Config changes and active-config changes will affect: $CONFIG_SOURCE_DIR"
fi
echo

export HOME="$DEV_HOME"
export R1SETUP_NO_VENV=1
export R1SETUP_SKIP_AUTO_UPDATE="${R1SETUP_SKIP_AUTO_UPDATE:-1}"
export R1SETUP_NO_CLEAR="${R1SETUP_NO_CLEAR:-1}"

exec "$PYTHON_BIN" "$REPO_R1SETUP" "${PASSTHROUGH_ARGS[@]}"
