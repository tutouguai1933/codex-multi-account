当前：这轮定位了 systemd 下额度全未知的根因，是服务环境里没有代理变量。现在 systemd service 会加载项目内环境文件，安装脚本也会把当前 shell 里的代理环境一起写进去。
停点：修复需要重新执行一次 `bash scripts/install-systemd-service.sh`，让环境文件写入并重启服务。仓库远程仍是 `https://github.com/tutouguai1933/codex-multi-account`。
决定：systemd 常驻运行不再只依赖最小环境，而是显式加载代理环境文件，避免 WSL 里“手动能检测、systemd 全未知”的差异。
