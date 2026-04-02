# Codex Multi Account Design

日期：2026-04-02

## 1. Summary

`codex-multi-account` 是一个运行在 Linux 上的本地 Web 服务，用来统一管理 `OpenClaw` 与 `Codex CLI` 的多账号登录态、状态检测、配额展示、手动切换与自动切换。

它要解决的问题是：单个 OpenAI/Codex 账号额度耗尽后，用户不只要切 `OpenClaw`，还往往要同时切 `Codex CLI`；如果两边长期共用同一个账号，又会加速额度消耗，导致频繁切号。

## 2. Goals

- 提供一个本地网页，展示 `OpenClaw` 与 `Codex CLI` 当前使用的账号、健康状态、额度状态和最近切换原因。
- 维护一个统一账号池，允许一个账号同时绑定 `OpenClaw`、`Codex CLI`，也允许只绑定其中一侧。
- 支持导入已有本地登录态，并能从界面触发 `OpenClaw` / `Codex CLI` 登录流程。
- 支持手动切换 `OpenClaw`、手动切换 `Codex CLI`，以及同时切换两侧。
- 支持定时刷新账号状态、配额与活跃会话信息。
- 支持自动切换，且默认优先让 `OpenClaw` 与 `Codex CLI` 分流到不同账号。
- 没有其他可用账号时，允许两侧落到同一个账号。
- 支持禁用账号、删除账号、查看最近事件与失败原因。

## 3. Non-goals

- 不做桌面壳，不做 Tauri/Electron 打包。
- 第一版不做远程部署，不做多机同步，只支持本机本地服务。
- 第一版不做多用户系统，不做权限分级。
- 第一版不做复杂通知中心，只保留基础事件日志与页面提示。
- 第一版不尝试直接解析或修改 OpenAI 线上账户信息，只依赖本地认证文件和可用的本地探测链路。

## 4. Current State

### 4.1 可复用链路

现有可复用实现位于：

- `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/SKILL.md`
- `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/scripts/openclaw-openai-accounts.py`
- `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/scripts/test_openclaw_openai_accounts.py`

它已经跑通并验证了这些能力：

- 从 `~/.openclaw/agents/<agent>/agent/auth-profiles.json` 识别真实活跃的 `openai-codex:default`
- 修复 `~/.openclaw/openclaw.json` 中的 `auth.profiles` 与 `auth.order`
- 在多个 agent 之间同步 `openai-codex:default` 与邮箱别名 profile
- 保存账号快照到 `~/.openclaw/openai-codex-accounts/profiles/*.json`
- 通过 usage API 获取 5 小时 / 周级别的额度信息
- 基于阈值、活跃 session、fallback model 做自动切换

### 4.2 本机环境事实

本机已确认存在：

- `python3`
- `node`
- `npm`
- `pnpm`
- `openclaw`
- `codex`

本机已确认 `Codex CLI` 当前活跃登录态位于：

- `~/.codex/auth.json`

本机已确认当前 `Codex CLI` 的账号快照目录为空：

- `~/.codex/accounts/`

结论：`Codex CLI` 侧第一版不能依赖已有账号池目录，需要服务自己维护快照。

## 5. Constraints

- 当前目录 `/home/djy/codex-multi-account` 还不是 git 仓库。
- 本地服务必须以“最小侵入”方式修改现有 `~/.openclaw` 与 `~/.codex` 状态文件。
- 账号快照与元数据属于敏感凭证，落盘权限应保持严格限制，例如 `0600`。
- 自动切换不能在软阈值场景里粗暴打断仍在活跃的用户会话。
- 用户希望参考 `cockpit-tools` 的产品能力，但当前设计应基于本地已验证链路，不依赖对方仓库实现细节。

## 6. Product Decisions

### 6.1 产品形态

- 第一版为纯本地 Web 服务。
- 服务启动后开放本地 HTTP 地址，前端通过浏览器访问。
- 不做桌面壳。

### 6.2 账号模型

- 维护一个统一账号池。
- `OpenClaw` 与 `Codex CLI` 都是账号池的消费者。
- 一个账号可以：
  - 同时绑定 `OpenClaw` 与 `Codex CLI`
  - 只绑定 `OpenClaw`
  - 只绑定 `Codex CLI`

### 6.3 自动调度策略

默认采用“先分流，再按健康度排序”的混合策略：

1. 过滤不可用账号
2. 优先排除另一个客户端当前已占用的账号
3. 在剩余候选集合里按额度、健康度、最近使用情况排序
4. 若无其他候选账号，允许两个客户端共用同一个账号

### 6.4 入池方式

第一版支持两类入池方式：

- 导入已有本地活跃登录态
- 从界面触发 `OpenClaw` / `Codex CLI` 登录流程并收编结果

### 6.5 账号生命周期动作

第一版支持：

- 导入
- 登录接入
- 手动切换
- 探测状态
- 禁用 / 启用
- 删除

## 7. Recommended Architecture

推荐采用 `Python 后端 + React 前端`：

- 后端：`FastAPI` + `Uvicorn`
- 前端：`React` + `TypeScript` + `Vite`

原因：

- 现有最复杂、最可靠的可复用逻辑在 Python 脚本中，直接抽成 Python 模块成本最低。
- 本地系统文件操作、定时任务、文件锁、子进程登录触发等都更适合保留在 Python 服务层。
- 前端只负责可视化与操作，不承担核心状态机职责。

### 7.1 服务层分解

- `runtime adapters`
  - `openclaw adapter`
  - `codex adapter`
- `account pool`
- `scheduler`
- `api server`
- `event store`

### 7.2 运行时高层数据流

1. 服务读取本地 `OpenClaw` / `Codex CLI` 状态
2. adapter 生成标准化的运行时快照
3. account pool 将快照映射到统一账号实体
4. scheduler 基于策略判断是否切换
5. 若需切换，adapter 回写对应运行时文件
6. API 将状态、事件、错误信息暴露给前端

## 8. Data Model

统一账号池中的单个账号建议包含：

```json
{
  "id": "acct_001",
  "label": "work-main",
  "email": "user@example.com",
  "tags": ["team", "primary"],
  "bindings": {
    "openclaw": {
      "snapshotId": "oc_work_main",
      "available": true
    },
    "codex": {
      "snapshotId": "cx_work_main",
      "available": true
    }
  },
  "status": {
    "health": "healthy",
    "reason": "live-usage-api",
    "manualDisabled": false
  },
  "quota": {
    "fiveHourUsedPct": 61.0,
    "weeklyUsedPct": 41.0,
    "resetAt": {
      "fiveHour": 1770000000,
      "weekly": 1770600000
    }
  },
  "assignment": {
    "openclaw": true,
    "codex": false
  },
  "timestamps": {
    "lastDetectedAt": 1770000000,
    "lastAssignedAt": 1770000001
  }
}
```

### 8.1 健康状态枚举

- `healthy`
- `auth-invalid`
- `plan-unavailable`
- `quota-unknown`
- `missing-binding`
- `manual-disabled`
- `stale`

## 9. Runtime Storage

项目自身维护的状态目录建议为：

- `./data/`

其中包含：

- `./data/accounts.json`
- `./data/settings.json`
- `./data/events/events.jsonl`
- `./data/snapshots/openclaw/*.json`
- `./data/snapshots/codex/*.json`
- `./data/runtime/*.json`
- `./data/locks/*.lock`

选择项目内 `data/` 而不是额外写入用户 home 的原因是：

- 当前项目就是一个本地控制面板
- 便于调试、备份、迁移
- 对第一版开发最直接

## 10. API Surface

### 10.1 Overview

- `GET /api/overview`
- `GET /api/accounts`
- `GET /api/accounts/:id`
- `GET /api/events`
- `GET /api/settings`

### 10.2 Account actions

- `POST /api/accounts/import/openclaw-current`
- `POST /api/accounts/import/codex-current`
- `POST /api/accounts/login/openclaw`
- `POST /api/accounts/login/codex`
- `POST /api/accounts/:id/probe`
- `POST /api/accounts/:id/switch`
- `POST /api/accounts/:id/disable`
- `POST /api/accounts/:id/enable`
- `DELETE /api/accounts/:id`

### 10.3 Scheduler actions

- `POST /api/scheduler/run`
- `POST /api/scheduler/refresh`

## 11. UI Information Architecture

### 11.1 Dashboard

- `OpenClaw` 当前账号卡片
- `Codex CLI` 当前账号卡片
- 当前是否分流
- 最近调度结果
- 5 小时 / 周额度可视化

### 11.2 Accounts

账号池表格每行展示：

- 标签
- 邮箱
- `OpenClaw` 绑定状态
- `Codex CLI` 绑定状态
- 健康状态
- 5 小时额度
- 周额度
- 最近刷新时间
- 当前分配目标
- 操作按钮

### 11.3 Settings

- 自动刷新开关
- 刷新周期
- `OpenClaw` 切换阈值
- `Codex CLI` 切换阈值
- 分流优先开关
- 允许共用账号的降级策略
- `OpenClaw` fallback model

### 11.4 Events

- 最近切换
- 被阻止的切换
- 认证失效
- 手动操作
- 删除与恢复失败

## 12. File Layout Proposal

```text
/home/djy/codex-multi-account
├── backend/
│   ├── pyproject.toml
│   ├── src/codex_multi_account/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── services/
│   │   ├── adapters/
│   │   ├── scheduler/
│   │   ├── storage/
│   │   └── api/
│   └── tests/
├── web/
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   └── public/
├── docs/
├── plans/
└── data/
```

## 13. Risks

- `Codex CLI` 登录流程的可脚本化程度可能低于 `OpenClaw`
- `Codex CLI` 的额度探测链路可能与 `OpenClaw` 侧不完全一致
- 直接改写 `~/.codex/auth.json` 需要非常严格的原子写与备份策略
- 自动切换如果缺乏冷却机制，可能导致两侧来回抖动
- 页面如果只展示“结果”而不展示“原因”，会让自动调度难以信任

## 14. Risk Mitigations

- 所有敏感文件写入采用原子替换
- 写入前生成最小必要备份
- 调度器增加冷却时间与事件日志
- 所有自动切换结果都记录“为什么切”与“为什么没切”
- 先把 `OpenClaw` 现有回归测试迁移过来，再扩展到 `Codex CLI`

## 15. Implementation Recommendation

先做后端，后做前端：

1. 抽离 OpenClaw 现有逻辑为 Python 模块
2. 增加 Codex adapter 与快照机制
3. 实现统一账号池和分流调度器
4. 提供 API
5. 最后做网页

这是最快拿到稳定内核的路线。

## 16. Open Questions

- `Codex CLI` 登录流程是否可以稳定地由服务端子进程触发并接管结果，需要在实现期验证
- `Codex CLI` 是否需要独立 fallback 策略，还是第一版先只对 `OpenClaw` 提供 fallback model

## 17. References

- `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/scripts/openclaw-openai-accounts.py`
- `/home/djy/.openclaw/workspace-taizi/skills/openclaw-openai-multi-account/scripts/test_openclaw_openai_accounts.py`
- `~/.openclaw/openclaw.json`
- `~/.openclaw/agents/*/agent/auth-profiles.json`
- `~/.codex/auth.json`
