# Codex Runtime Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `codex-multi-account` 增加一个 `Codex` 配置文件编辑页，并把当前会话的 `resume` 归属迁到项目目录。

**Architecture:** 后端新增 `Codex` 原文读写与快捷字段接口，前端设置页新增 `Codex 文件` 面板；同时调整当前会话的 `cwd` 元数据，让 `codex resume` 在项目目录下可见。

**Tech Stack:** Python 3、FastAPI、pytest、React、TypeScript、Vite

---

## Tasks

### Task 1: 写失败测试覆盖 Codex 文件接口

- [ ] 增加读取原文接口测试
- [ ] 增加保存原文接口测试
- [ ] 增加快捷字段更新接口测试

### Task 2: 实现后端接口

- [ ] 在 `CodexCliAdapter` 中补齐原文读写能力
- [ ] 在 `routes_settings.py` 中补齐 `Codex` 文件路由
- [ ] 回跑后端相关测试

### Task 3: 实现设置页

- [ ] 在设置页新增 `Codex 文件` 面板
- [ ] 接入快捷字段和原文编辑接口
- [ ] 构建前端

### Task 4: 迁移当前会话归属

- [ ] 把当前线程的 `cwd` 元数据迁到 `/home/djy/codex-multi-account`
- [ ] 验证在项目目录下执行 `codex resume` 可以看到这条会话

### Task 5: 真实验证和记录更新

- [ ] 重启 `systemd` 服务
- [ ] 真实页面验证快捷字段修改和原文保存
- [ ] 更新 `CONTEXT.md`、`README.md`、`ARCHITECTURE.md`
