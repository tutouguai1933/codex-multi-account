#!/usr/bin/env bash
# 这个脚本负责统一启动 codex-multi-account，供 systemd 和手动启动共用。

set -euo pipefail

# 输出一行用法说明。
usage() {
  cat <<'EOF'
用法：
  bash scripts/run-codex-multi-account.sh [--dry-run]

说明：
  --dry-run   只打印解析后的启动参数，不真正启动服务
EOF
}

# 解析启动参数。
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

# 输出当前解析到的关键信息。
print_summary() {
  cat <<EOF
repo_root=${CMA_ROOT}
backend_dir=${BACKEND_DIR}
pythonpath=${PYTHONPATH_VALUE}
host=${CMA_HOST}
port=${CMA_PORT}
data_dir=${CMA_DATA_DIR}
conda_env=${CMA_ENV_NAME}
EOF
}

# 激活 conda 环境。
activate_conda_env() {
  local conda_script="${CMA_CONDA_SCRIPT}"
  if [[ ! -f "${conda_script}" ]]; then
    echo "未找到 conda 初始化脚本：${conda_script}" >&2
    exit 1
  fi

  # shellcheck source=/dev/null
  source "${conda_script}"
  conda activate "${CMA_ENV_NAME}"
}

parse_args "$@"

CMA_ROOT="${CMA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CMA_HOST="${CMA_HOST:-127.0.0.1}"
CMA_PORT="${CMA_PORT:-9001}"
CMA_ENV_NAME="${CMA_ENV_NAME:-codex-multi-account}"
CMA_CONDA_SCRIPT="${CMA_CONDA_SCRIPT:-/home/djy/miniforge3/etc/profile.d/conda.sh}"
CMA_DATA_DIR="${CMA_DATA_DIR:-${CMA_ROOT}/data}"
BACKEND_DIR="${CMA_ROOT}/backend"
PYTHONPATH_VALUE="${BACKEND_DIR}/src"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "未找到 backend 目录：${BACKEND_DIR}" >&2
  exit 1
fi

mkdir -p "${CMA_DATA_DIR}"

if [[ "${DRY_RUN}" == "1" ]]; then
  print_summary
  exit 0
fi

activate_conda_env
cd "${BACKEND_DIR}"
export CMA_DATA_DIR
export PYTHONPATH="${PYTHONPATH_VALUE}"

exec python -m uvicorn codex_multi_account.app:create_app --factory --host "${CMA_HOST}" --port "${CMA_PORT}"
