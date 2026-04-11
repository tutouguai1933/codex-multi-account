// 这个文件集中处理所有 HTTP 请求，页面只关心数据和动作本身。

import type {
  AccountRecord,
  ApiAccountPayload,
  CodexQuickSettings,
  CodexRuntimeFiles,
  EventRecord,
  LoginSessionState,
  OverviewResponse,
  SchedulerSettings,
  SwitchPayload,
} from "./types";

function normalizeNetworkError(error: unknown): Error {
  if (error instanceof Error) {
    if (error.message === "Failed to fetch") {
      return new Error("本地服务未连接，请确认 9001 服务正在运行");
    }
    return error;
  }
  return new Error("本地服务未连接，请确认 9001 服务正在运行");
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? undefined);
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(input, {
      headers,
      ...init,
    });
  } catch (error) {
    throw normalizeNetworkError(error);
  }
  if (!response.ok) {
    let detail = `request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // 这里保持默认错误信息即可。
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getOverview(): Promise<OverviewResponse> {
  return requestJson<OverviewResponse>("/api/overview");
}

export async function listAccounts(): Promise<AccountRecord[]> {
  const payload = await requestJson<{ accounts: AccountRecord[] }>("/api/accounts");
  return payload.accounts;
}

export async function listEvents(): Promise<EventRecord[]> {
  const payload = await requestJson<{ events: EventRecord[] }>("/api/events");
  return payload.events;
}

export async function getSettings(): Promise<SchedulerSettings> {
  return requestJson<SchedulerSettings>("/api/settings");
}

export async function saveSettings(
  settings: SchedulerSettings,
): Promise<SchedulerSettings> {
  return requestJson<SchedulerSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function getCodexRuntimeFiles(): Promise<CodexRuntimeFiles> {
  return requestJson<CodexRuntimeFiles>("/api/settings/codex-runtime");
}

export async function saveCodexRuntimeFiles(payload: {
  config_text: string;
  auth_text: string;
}): Promise<CodexRuntimeFiles> {
  return requestJson<CodexRuntimeFiles>("/api/settings/codex-runtime", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function saveCodexQuickSettings(
  payload: Partial<CodexQuickSettings>,
): Promise<CodexRuntimeFiles> {
  return requestJson<CodexRuntimeFiles>("/api/settings/codex-runtime/quick", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function importCurrent(target: "openclaw" | "codex", label?: string) {
  return requestJson<AccountRecord>(`/api/accounts/import/${target}-current`, {
    method: "POST",
    body: JSON.stringify({ label }),
  });
}

export async function importCodexBatch(items: Array<Record<string, unknown>>) {
  return requestJson<{ importedCount: number; accounts: AccountRecord[] }>(
    "/api/accounts/import/codex-batch",
    {
      method: "POST",
      body: JSON.stringify({ items }),
    },
  );
}

export async function importTokenPayload(value: string, label?: string) {
  return requestJson<{ importedCount: number; accounts: AccountRecord[] }>(
    "/api/accounts/import/token",
    {
      method: "POST",
      body: JSON.stringify({ value, label }),
    },
  );
}

export async function createApiAccount(payload: ApiAccountPayload) {
  return requestJson<AccountRecord>("/api/accounts/import/api-account", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function exportCodexBatch() {
  return requestJson<{ items: Array<Record<string, unknown>> }>(
    "/api/accounts/export/codex-batch",
  );
}

export async function startLogin(target: "openclaw" | "codex") {
  return requestJson<LoginSessionState>(
    `/api/accounts/login/${target}`,
    {
      method: "POST",
    },
  );
}

export async function listLoginStates() {
  return requestJson<{ targets: Record<"openclaw" | "codex", LoginSessionState> }>(
    "/api/accounts/logins",
  );
}

export async function cancelLogin(target: "openclaw" | "codex") {
  return requestJson<LoginSessionState>(`/api/accounts/login/${target}/cancel`, {
    method: "POST",
  });
}

export async function submitLoginInput(
  target: "openclaw" | "codex",
  value: string,
) {
  return requestJson<LoginSessionState>(`/api/accounts/login/${target}/input`, {
    method: "POST",
    body: JSON.stringify({ value }),
  });
}

export async function probeAccount(accountId: string) {
  return requestJson<AccountRecord>(`/api/accounts/${accountId}/probe`, {
    method: "POST",
  });
}

export async function switchAccount(accountId: string, payload: SwitchPayload) {
  return requestJson<{ accountId: string; target: string; status: string }>(
    `/api/accounts/${accountId}/switch`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function disableAccount(accountId: string) {
  return requestJson<AccountRecord>(`/api/accounts/${accountId}/disable`, {
    method: "POST",
  });
}

export async function enableAccount(accountId: string) {
  return requestJson<AccountRecord>(`/api/accounts/${accountId}/enable`, {
    method: "POST",
  });
}

export async function deleteAccount(accountId: string) {
  return requestJson<{ status: string }>(`/api/accounts/${accountId}`, {
    method: "DELETE",
  });
}

export async function runScheduler() {
  return requestJson<{
    assignments: Record<string, string | null>;
    actions: Record<string, string>;
    reason: string;
    forcedImmediate: boolean;
  }>("/api/scheduler/run", {
    method: "POST",
  });
}

export async function refreshAllQuotas() {
  return requestJson<{ status: string }>("/api/scheduler/refresh", {
    method: "POST",
  });
}
