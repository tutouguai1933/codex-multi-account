#!/usr/bin/env bash
# 这个脚本负责安装 systemd 服务，让 codex-multi-account 随 WSL 启动。

set -euo pipefail

SERVICE_NAME="codex-multi-account.service"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_FILE="${REPO_ROOT}/deploy/systemd/${SERVICE_NAME}"
TARGET_FILE="/etc/systemd/system/${SERVICE_NAME}"

# 输出用法。
usage() {
  cat <<'EOF'
用法：
  sudo bash scripts/install-systemd-service.sh [--dry-run]

说明：
  --dry-run   只打印将要执行的目标路径，不真正安装
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

parse_args "$@"

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "未找到 service 文件：${SOURCE_FILE}" >&2
  exit 1
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  cat <<EOF
source=${SOURCE_FILE}
target=${TARGET_FILE}
EOF
  exit 0
fi

if [[ "$(id -u)" != "0" ]]; then
  echo "请用 sudo 运行这个脚本。" >&2
  exit 1
fi

cp "${SOURCE_FILE}" "${TARGET_FILE}"
systemctl daemon-reload
systemctl enable --now codex-multi-account
systemctl status codex-multi-account --no-pager
