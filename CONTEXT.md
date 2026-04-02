当前：这轮开始补 WSL 常驻启动能力，已经加了统一启动脚本、systemd 安装脚本和登录启动脚本，并把 systemd 文件改成调用统一启动入口。
停点：仓库远程仍是 `https://github.com/tutouguai1933/codex-multi-account`。当前沙箱里的 PID 1 不是 systemd，所以这里只能验证脚本语法和 dry-run，不能直接在这个环境里跑真实的 systemctl。
决定：WSL 常驻运行同时保留 `systemd` 和登录启动脚本两条路径，但两者共用 `scripts/run-codex-multi-account.sh`，避免维护两套不同命令。
