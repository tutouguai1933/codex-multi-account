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

仓库里已经提供了一个示例服务文件：

`/home/djy/codex-multi-account/deploy/systemd/codex-multi-account.service`

使用前请先确认里面的路径和用户名仍然符合当前机器，然后执行：

```bash
sudo cp /home/djy/codex-multi-account/deploy/systemd/codex-multi-account.service /etc/systemd/system/codex-multi-account.service
sudo systemctl daemon-reload
sudo systemctl enable --now codex-multi-account
```

查看状态：

```bash
systemctl status codex-multi-account --no-pager
```
