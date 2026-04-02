# 运行说明

## 1. 激活环境

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate codex-multi-account
```

## 2. 启动后端

```bash
cd /home/djy/codex-multi-account/backend
PYTHONPATH=/home/djy/codex-multi-account/backend/src python3 -m uvicorn codex_multi_account.app:create_app --factory --host 127.0.0.1 --port 9001
```

## 3. 启动前端

先由你安装依赖：

```bash
cd /home/djy/codex-multi-account/web
pnpm install
```

再启动：

```bash
pnpm dev
```

## 3.1 单服务模式

如果你希望更接近长期运行，而不是一直开着前端开发服务，可以先构建前端：

```bash
cd /home/djy/codex-multi-account/web
pnpm build
```

然后只启动后端。此时后端会直接托管 `web/dist`，浏览器打开：

```text
http://127.0.0.1:9001/
```

预期结果：
- 页面可以直接从 `9001` 打开
- 不需要再单独启动 `pnpm dev`
- 页面里的 `/api` 请求会直接走同一个服务

## 4. 常用动作

- 导入当前 OpenClaw：页面“账户”里点“导入当前 OpenClaw”
- 导入当前 Codex：页面“账户”里点“导入当前 Codex”
- 发起登录：页面“账户”里点“开始 OpenClaw 登录”或“开始 Codex 登录”
  - 页面会显示当前登录状态、PID、授权链接和最近输出摘要
  - 打开授权链接后，可以把完整回调地址或授权码直接粘贴回页面里的“提交授权信息”
  - 如果流程卡住，可以直接在页面点“取消登录”
  - 如果服务重启，上一次未完成的登录会显示为 `interrupted`
  - 如果 CLI 回显了带授权码的回调地址，页面和本地状态会自动隐藏敏感参数
  - 注意：第一版仍然要在浏览器里走完外部 OAuth 授权页，但回调地址已经不用再手动粘到服务终端
- 手动切换：页面“账户”里点“切 OpenClaw”或“切 Codex”
- 状态检测：页面“账户”里点“检测”

## 5. 后端测试

```bash
cd /home/djy/codex-multi-account
python3 -m pytest backend/tests -q
```

## 6. systemd 常驻运行

如果你的 WSL 已经打开了 `systemd`，可以直接用仓库里的安装脚本：

```bash
cd /home/djy/codex-multi-account
bash scripts/install-systemd-service.sh
```

这个安装脚本会把你当前 shell 里的代理环境一起写进 service 使用的环境文件，避免 systemd 服务因为拿不到 `HTTP_PROXY/HTTPS_PROXY` 而探测不到额度。

如果只想先看安装目标而不真正执行：

```bash
cd /home/djy/codex-multi-account
bash scripts/install-systemd-service.sh --dry-run
```

仓库里也保留了原始 service 文件：

`/home/djy/codex-multi-account/deploy/systemd/codex-multi-account.service`

查看状态：

```bash
systemctl status codex-multi-account --no-pager
```

## 7. 没开 systemd 时的启动脚本

如果你的 WSL 没开 `systemd`，可以用登录启动脚本：

```bash
cd /home/djy/codex-multi-account
bash scripts/start-on-wsl-login.sh
```

它会先检查 `9001` 是否已经在监听，只有没启动时才会后台拉起服务。

如果你想把它放进 WSL 登录流程，可以把这一行加入 `~/.bashrc` 或 `~/.profile`：

```bash
bash /home/djy/codex-multi-account/scripts/start-on-wsl-login.sh
```

如果只想查看脚本会使用哪些参数：

```bash
cd /home/djy/codex-multi-account
bash scripts/start-on-wsl-login.sh --dry-run
```
