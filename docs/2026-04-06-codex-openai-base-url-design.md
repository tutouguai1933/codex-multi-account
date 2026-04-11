# Codex OpenAI Base URL Design

日期：2026-04-06

## 1. Summary

把 `codex-multi-account` 的第三方 API 账号切换方式改成内置 `openai` 路线：`Codex CLI` 只写 `openai_base_url` 和 `auth.json` 里的 `OPENAI_API_KEY`，不再改 `model_provider` 身份。

这样做的原因是：当前把第三方接口写成自定义 provider 后，`Codex CLI` 的历史会话会因为 provider 名不一致而在 `resume` 里消失；改成内置 `openai` 路线后，历史会话和后续会话会保持同一身份。

## 2. Goals

- 让 `Codex CLI` 在第三方 API 模式下仍保持 `openai` 身份，不再影响 `codex resume`
- 第三方 API 账号继续进入统一账号池，并且 `Codex CLI` 和 `OpenClaw` 都能切换使用
- 账户页新增第三方 API 时只保留两个输入：基础地址、API Key
- 第三方 API 账号的显示名称直接使用基础地址
- 切换第三方 API 账号时，不再改动模型、推理强度、上下文窗口等通用设置

## 3. Non-goals

- 不改自动调度规则
- 不新增新的第三方 provider 类型
- 不改 OAuth / Token 导入流程
- 不改 `OpenClaw` 现有 OAuth 链路

## 4. Design

### 4.1 Codex CLI 侧

- `config.toml` 保持内置 `openai` 路线
- 第三方 API 激活时，只写：
  - `openai_base_url`
  - `model`
  - `auth.json` 中的 `auth_mode=apikey`
  - `auth.json` 中的 `OPENAI_API_KEY`
- 不再写：
  - `model_provider`
  - `[model_providers.*]`
  - 其他自定义 provider 配置

### 4.2 第三方 API 账号模型

- 账号池内仍保留 `ApiProfile`
- 但输入面只要求：
  - `base_url`
  - `api_key`
- 其他值改成后端内部默认：
  - `provider_name = "openai"`
  - `model = "gpt-5.4"`
  - `wire_api = "responses"`
- 账号 label 默认跟随 `base_url`

### 4.3 OpenClaw 侧

- 继续沿用当前 API 快照写法
- 从统一账号池读取 `base_url` 和 `api_key`
- 继续生成 OpenClaw 可识别的 API profile

## 5. Risks

- 旧的 `OpenAI` / `openai-custom` 会话如果不统一回 `openai`，`resume` 仍会分堆显示
- `Codex CLI` 当前版本如果对 `openai_base_url` 的兼容有边界，切换后需要做真实验证
- 前端删掉高级配置后，已有测试和类型需要同步更新

## 6. Validation

- `codex resume --all` 能重新列出旧会话
- `backend/tests` 中相关 API 账号测试通过
- 前端构建通过
- 页面真实新增第三方 API 账号后，只显示基础地址和 API Key 两个输入
- 手动切换到第三方 API 账号后，`Codex CLI` 和 `OpenClaw` 都能读到新配置
