# Codex OpenAI Base URL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把第三方 API 账号切换统一收口到内置 `openai + openai_base_url` 方案，并恢复 `codex resume` 可见性。

**Architecture:** 后端保留统一账号池和 OpenClaw API 快照逻辑，但 Codex CLI 不再写自定义 provider，只写 `openai_base_url` 和 API key 登录态。前端第三方 API 表单收缩成两个字段，默认值交给后端维护。

**Tech Stack:** Python 3、FastAPI、pytest、React、TypeScript、Vite

---

## Scope

- 修正本机 `~/.codex` 配置与历史会话 provider 归一化
- 改造 `codex-multi-account` 的 Codex API 配置写法
- 简化第三方 API 账号表单和对应类型
- 更新测试与项目记录

## Out Of Scope

- 不改调度规则
- 不改 OAuth 登录流程
- 不新增新的 API 提供商类型

## Tasks

### Task 1: 写失败测试覆盖 Codex API 新写法

**Files:**
- Modify: `/home/djy/codex-multi-account/backend/tests/test_codex_cli_adapter.py`
- Modify: `/home/djy/codex-multi-account/backend/tests/test_account_pool.py`
- Modify: `/home/djy/codex-multi-account/backend/tests/test_api_accounts.py`

- [ ] 写失败测试，断言第三方 API 激活后 `config.toml` 使用 `openai_base_url`，而不是 `model_provider`
- [ ] 写失败测试，断言新增 API 账号时只需要 `base_url` 与 `api_key`
- [ ] 运行相关测试，确认按旧实现失败

### Task 2: 改造后端默认值与 Codex 配置写法

**Files:**
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/models/account.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/utils/api_profiles.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/adapters/codex_cli.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/services/account_pool.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/routes_accounts.py`
- Modify: `/home/djy/codex-multi-account/backend/src/codex_multi_account/api/serializers.py`

- [ ] 把第三方 API 默认 provider 身份固定成内置 `openai`
- [ ] 让 Codex 配置只写 `openai_base_url`
- [ ] 保持 `auth.json` 走 `apikey` 模式
- [ ] 让 API 账号 label 默认跟随基础地址
- [ ] 跑后端相关测试，确认通过

### Task 3: 改造前端表单和类型

**Files:**
- Modify: `/home/djy/codex-multi-account/web/src/components/AddAccountPanel.tsx`
- Modify: `/home/djy/codex-multi-account/web/src/lib/types.ts`
- Modify: `/home/djy/codex-multi-account/web/src/pages/AccountsPage.tsx`

- [ ] 删除第三方 API 的 provider 和高级配置输入
- [ ] 保留基础地址、API Key 两个输入
- [ ] 前端提交时只传需要的字段
- [ ] 构建前端，确认通过

### Task 4: 恢复本机 Codex provider 并做真实验证

**Files:**
- Modify: `/home/djy/.codex/config.toml`
- Modify: `/home/djy/.codex/state_5.sqlite`
- Modify: `/home/djy/.codex/sessions/**/*.jsonl`

- [ ] 先备份本机 Codex 配置与会话数据
- [ ] 把 provider 归一化为 `openai`
- [ ] 真实验证 `codex resume --all`
- [ ] 重启本地服务并做页面新增/切换验证

### Task 5: 更新项目记录

**Files:**
- Modify: `/home/djy/codex-multi-account/CONTEXT.md`
- Modify: `/home/djy/codex-multi-account/README.md`
- Modify: `/home/djy/codex-multi-account/ARCHITECTURE.md`

- [ ] 更新当前停点和关键决定
- [ ] 更新 README 的第三方 API 配置说明
- [ ] 更新架构说明，写清楚 Codex 侧现在走 `openai_base_url`
