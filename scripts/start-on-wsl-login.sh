#!/usr/bin/env bash
# 这个脚本用于没有 systemd 时，在登录 WSL 后自动拉起本地服务。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="${REPO_ROOT}/scripts/run-codex-multi-account.sh"
HOST="${CMA_HOST:-127.0.0.1}"
PORT="${CMA_PORT:-9001}"
LOG_DIR="${CMA_DATA_DIR:-${REPO_ROOT}/data}/logs"
LOG_FILE="${LOG_DIR}/startup.log"

# 输出用法。
usage() {
  cat <<'EOF'
用法：
  bash scripts/start-on-wsl-login.sh [--dry-run]

说明：
  这个脚本适合放进 ~/.bashrc 或 ~/.profile。
  它会在检测到 9001 未被占用时，在后台启动服务。
EOF
}

# 解析参数。
parse_args() {
  DRY_RUN="0"
  while (($# > 0)); do
    case "$1" in
      --dry-run)
        DRY_RUN="1"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数：$1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

# 检查端口是否已在监听。
is_port_active() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${PORT} )" | grep -q "${PORT}"
    return
  fi

  if command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | grep -q ":${PORT} "
    return
  fi

  return 1
}

parse_args "$@"

if [[ ! -f "${RUNNER}" ]]; then
  echo "未找到启动脚本：${RUNNER}" >&2
  exit 1
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  cat <<EOF
runner=${RUNNER}
host=${HOST}
port=${PORT}
log_file=${LOG_FILE}
EOF
  exit 0
fi

if is_port_active; then
  exit 0
fi

mkdir -p "${LOG_DIR}"
nohup bash "${RUNNER}" >>"${LOG_FILE}" 2>&1 </dev/null &
