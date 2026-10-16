import type {
  CarListResponse,
  EvaluationReport,
  ErrorCase,
  HealthResponse,
  KnowledgeGraphResponse,
  LLMConfigResponse,
  NlpAnalysis,
  PromptExperimentResponse,
  RagAnswerResponse,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const payload = (await response.json().catch(() => ({}))) as { detail?: string };
  if (!response.ok) {
    throw new Error(payload.detail ?? `API 请求失败：${response.status}`);
  }
  return payload as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  cars: () => request<CarListResponse>("/api/cars"),
  ask: (question: string, mode = "demo_grounded") =>
    request<RagAnswerResponse>("/api/qa/answer", {
      method: "POST",
      body: JSON.stringify({ question, mode }),
    }),
  graph: (carId?: string) =>
    request<KnowledgeGraphResponse>(
      `/api/knowledge/graph${carId ? `?car_id=${encodeURIComponent(carId)}` : ""}`,
    ),
  evaluation: () => request<EvaluationReport>("/api/evaluation/report"),
  errors: () => request<ErrorCase[]>("/api/evaluation/errors"),
  analyze: (text: string) =>
    request<NlpAnalysis>("/api/nlp/analyze", {
      method: "POST",
      body: JSON.stringify({ text, strategy: "rule_baseline" }),
    }),
  prompt: (text: string, strategyId: "A" | "B" | "C") =>
    request<PromptExperimentResponse>("/api/evaluation/prompt", {
      method: "POST",
      body: JSON.stringify({ text, strategy_id: strategyId }),
    }),
  llmSettings: () => request<LLMConfigResponse>("/api/settings/llm"),
  configureLLM: (config: { api_key: string; base_url: string; model: string; persist: boolean }) =>
    request<LLMConfigResponse>("/api/settings/llm", {
      method: "POST",
      body: JSON.stringify(config),
    }),
};
