# Codex Runtime Editor Design

日期：2026-04-06

## 1. Summary

在设置页新增一个只针对 `Codex` 的配置编辑区，既能直接查看和保存 `~/.codex/config.toml`、`~/.codex/auth.json` 原文，也能通过几个常用字段快速改基础设置。

## 2. Goals

- 页面里直接看到 `config.toml` 和 `auth.json` 当前内容
- 支持直接编辑原文并保存
- 支持快捷修改这些常用字段：
  - `openai_base_url`
  - `model`
  - `review_model`
  - `model_reasoning_effort`
  - `model_context_window`
  - `model_auto_compact_token_limit`
- 快捷修改后，原文编辑区立刻显示最新文件内容

## 3. Non-goals

- 先不做 `OpenClaw` 配置编辑
- 不做多文件版本管理
- 不做权限系统

## 4. Design

- 后端在 `/api/settings` 下新增 `Codex` 文件接口
- `GET` 返回：
  - `config_text`
  - `auth_text`
  - `quick_settings`
- `PUT /api/settings/codex-runtime` 保存原文
- `PUT /api/settings/codex-runtime/quick` 保存快捷字段
- 前端设置页新增 `Codex 文件` 面板：
  - 上半区是快捷字段
  - 下半区是两个原文文本框
  - 提供“应用基础设置”“重新读取文件”“保存文件”按钮

## 5. Validation

- 后端接口测试通过
- 前端构建通过
- 真实页面验证能看到新面板
- 真实页面验证快捷字段修改后原文会变化
- 真实页面验证原文保存后接口返回最新文本
