# 架构说明

## 模块职责

- `backend/src/codex_multi_account/config.py`
  - 管理项目路径、数据目录、OpenClaw/Codex 根目录和外部配置，并识别实际项目根目录
- `backend/src/codex_multi_account/models/`
  - 定义账号、事件、设置等共享模型
- `backend/src/codex_multi_account/storage/json_store.py`
  - 提供小体量 JSON 文档的原子读写
- `backend/src/codex_multi_account/storage/event_log.py`
  - 负责事件日志的追加和读取
- `backend/src/codex_multi_account/adapters/openclaw.py`
  - 读写 `~/.openclaw` 下的运行时文件和快照
- `backend/src/codex_multi_account/adapters/codex_cli.py`
  - 读写 `~/.codex/auth.json` 和 Codex 快照，并负责把 `cockpit-tools` 导出条目转成可切换的 auth 结构，以及把 `last_refresh` 规整成 CLI 可接受的 RFC 3339 时间字符串
- `backend/src/codex_multi_account/services/account_pool.py`
  - 维护统一账号池，处理单个导入、批量导入/导出、禁用、删除和目标分配
- `backend/src/codex_multi_account/services/probe_service.py`
  - 负责共享账号状态检测和额度探测，会尝试两侧绑定并按窗口时长解析 5h/week
- `backend/src/codex_multi_account/services/switch_service.py`
  - 负责把指定账号切到 OpenClaw、Codex 或两边同时切
- `backend/src/codex_multi_account/services/login_session.py`
  - 负责用 PTY 启动登录命令、持久化登录状态、提取授权链接、接收页面提交的授权信息、遮掉敏感回调参数、支持取消，并在成功后尝试自动收编当前登录态
- `backend/src/codex_multi_account/scheduler/engine.py`
  - 负责自动调度，优先分流，并结合 5h/week 阈值决定 keep、switch 或阻塞；手动立即调度时会走强制重算
- `backend/src/codex_multi_account/scheduler/runner.py`
  - 负责后台自动刷新循环、立即执行一次调度、最近状态记录，以及单次失败后的循环保活
- `backend/src/codex_multi_account/api/`
  - 暴露总览、账号、登录状态、设置、事件、调度状态和手动调度接口；批量刷新额度会以后台任务方式启动
- `backend/src/codex_multi_account/api/serializers.py`
  - 负责把账号模型转成前端可展示的安全结构，过滤掉 token 等敏感字段
- `backend/src/codex_multi_account/app.py`
  - 组装整个 FastAPI 应用，并在存在前端构建产物时托管静态页面
- `web/src/App.tsx`
  - 管理页面切换、侧边导航和顶栏状态，并接收总览页回传的最新概览数据
- `web/src/pages/`
  - 展示总览、账号、事件、设置四个页面，其中总览页负责运维面板、运行面板和全局动作，账户页还负责批量导入/导出 JSON
- `web/src/components/AccountCard.tsx`
  - 渲染总览页的账号卡片，集中显示状态、额度、当前分配和图标操作按钮
- `web/src/lib/api.ts`
  - 统一封装前端 HTTP 请求
- `web/src/lib/types.ts`
  - 定义前后端共享的前端类型

## 调用关系

1. 页面调用 `web/src/lib/api.ts`
2. API 请求进入 `backend/src/codex_multi_account/api/`
3. 路由调用 `services/`
4. `services/` 需要时调用 `adapters/` 和 `storage/`
5. `scheduler/runner.py` 在后台周期性调用 `scheduler/engine.py`
6. `scheduler/engine.py` 使用 `probe_service`、`switch_service` 和 `event_log`
7. `login_session.py` 启动登录命令，并在命令退出后调用 `account_pool` 自动收编
8. 账户页提交的回调地址会走 `routes_accounts.py -> login_session.py -> PTY 登录进程`
9. 登录状态会落到 `data/login_sessions.json`，服务重启后重新加载

## 关键设计决定

- 后端继续用 Python，是因为现有 OpenClaw 多账号脚本已经在 Python 里跑通
- `Codex CLI` 不依赖 `~/.codex/accounts`，而是自己维护快照目录
- 账号池按“一个账号可绑定 OpenClaw、Codex 任意一侧或两侧”设计
- 自动调度默认优先把 `OpenClaw` 和 `Codex CLI` 分配到不同账号
- 账号健康状态继续按“一个真实账号一份共享状态”建模，但探测时会尝试两侧绑定，避免被单侧旧快照误伤
- 批量导入时会把 `cockpit-tools` 原始条目拆成“Codex 快照 + OpenClaw 快照 + 本地导出元数据”，避免把运行时认证文件写成不兼容格式
- 账号去重不再只按邮箱，而是优先按 `account_id + user_id`，减少同邮箱不同 workspace 被误合并
- 前端看到的账号元数据必须先经过脱敏，只保留工作区、套餐、账号身份和时间戳，不把 token 送到浏览器
- 项目内状态写到 `data/`，方便调试和迁移
- 自动刷新状态直接由后端返回给总览页，避免页面自己猜测后台是否在运行
- 总览除了 `separated` 之外，还返回 `allocationMode`，让页面能区分未分配、部分分配、共用和分流
- 总览页现在只吃一份 `overview` 数据；后端会按真实运行态识别当前 OpenClaw/Codex 账号，并覆盖首页卡片里的 assignment 显示，避免旧分配缓存把当前账号显示错
- 前端首页按“运维控制台”设计：顶部只放分配、风险、调度和结果，不再出现说明式长文案；账号区保持高密度卡片墙
- 运行面板拆成“当前账号 + 运行状态”两区，减少拥挤感，同时保留高密度信息
- 卡片里的常用动作改成图标按钮，悬停再显示说明，把空间优先留给状态、额度和当前分配
- 首页动作完成后会把最新概览同步回应用外壳，避免顶栏和页面主体显示不一致
- 删除账号必须先确认，避免卡片页误删
- 时间展示统一固定成中文 24 小时格式，避免系统默认语言把同一页面显示成中英文混排
- 手动“立即调度一次”和后台自动轮询不再完全同策略：前者用于立刻重算最优账号，后者继续按阈值保守切换
- OpenClaw 在挑选新账号时也会先避开当前正在给 Codex 使用的账号，避免手动重算时把分流结果重新挤回同一账号
- “一键检测所有额度”不再阻塞前端等待所有账号都探测完成，而是先返回“已开始”，再由页面稍后自动刷新，避免首页长时间卡住
- 项目统一固定使用 `9001` 作为主服务端口，前端开发代理也直接指向 `9001`
- 单服务模式下由后端直接托管 `web/dist`，更适合常驻运行
- 登录流程先做成“页面可见状态 + 授权链接 + 页面提交授权信息 + 本机 CLI 执行”，在不破坏现有 CLI 链路的前提下逐步收口
