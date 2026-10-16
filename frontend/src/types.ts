export type ViewKey = "qa" | "graph" | "evaluation" | "errors" | "prompt";

export interface HealthResponse {
  status: string;
  service: string;
  database: string;
  data_mode: string;
  car_count: number;
}

export interface CarOpinion {
  attribute: string;
  sentiment: string;
  text: string;
  source_name: string;
  collected_at: string;
}

export interface CarRecord {
  id: string;
  brand: string;
  model: string;
  version?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  energy_type: string;
  body_type: string;
  range_km?: number | null;
  usage_scenarios: string[];
  highlights: string[];
  opinions: CarOpinion[];
  source_name: string;
  source_url?: string | null;
  collected_at: string;
  data_status: string;
  source_type: string;
}

export interface CarListResponse {
  total: number;
  data_mode: string;
  cars: CarRecord[];
}

export interface ConstraintRecord {
  field: string;
  operator: string;
  value: string | number;
  source_text: string;
}

export interface ExtractedEntities {
  brands: string[];
  models: string[];
  budget_min?: number | null;
  budget_max?: number | null;
  energy_type?: string | null;
  body_type?: string | null;
  range_min_km?: number | null;
  usage_scenarios: string[];
  configurations: string[];
  focus_attributes: string[];
  hard_constraints: ConstraintRecord[];
  soft_preferences: ConstraintRecord[];
  negative_constraints: ConstraintRecord[];
  ambiguous_mentions: string[];
  unrecognized_mentions: string[];
}

export interface NlpAnalysis {
  text: string;
  intent: string;
  intent_evidence: string[];
  entities: ExtractedEntities;
  strategy: string;
  parser_status: string;
  raw_output?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  car_id?: string | null;
  subject: string;
  field: string;
  value: unknown;
  statement: string;
  provenance: {
    source_name: string;
    source_url?: string | null;
    collected_at: string;
    data_status: string;
    source_type: string;
  };
}

export interface RagAnswerResponse {
  question: string;
  analysis: NlpAnalysis;
  evidence: EvidenceItem[];
  answer: string;
  citations: string[];
  mode: string;
  grounded: boolean;
  refusal_reason?: string | null;
  parser_status: string;
  raw_output?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  provenance: {
    source_name: string;
    source_url?: string | null;
    collected_at: string;
    data_status: string;
    source_type: string;
  };
}

export interface KnowledgeGraphResponse {
  data_mode: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EvaluationSummary {
  status: string;
  sample_count: number;
  completed_count: number;
  accuracy?: number | null;
  macro_f1?: number | null;
  entity?: {
    precision?: number;
    recall?: number;
    f1?: number;
  } | null;
  error_count: number;
  latency_ms: { average?: number | null; p95?: number | null };
  tokens: { input_total?: number | null; output_total?: number | null };
  confusion_matrix?: Record<string, Record<string, number>>;
  per_intent_accuracy?: Record<string, number>;
}

export interface EvaluationReport {
  dataset_type: string;
  rule_baseline: EvaluationSummary;
  prompt_strategies: Array<{
    strategy_id: string;
    version: string;
    name: string;
    status: string;
    metrics?: EvaluationSummary | null;
  }>;
  report_path?: string | null;
}

export interface ErrorCase {
  strategy_id: string;
  sample_id: string;
  text: string;
  expected_intent: string;
  predicted_intent?: string | null;
  error_type: string;
  error_message?: string;
}

export interface PromptExperimentResponse {
  strategy_id: string;
  prompt_version: string;
  text: string;
  intent: string;
  entities: Record<string, unknown>;
  raw_output?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  latency_ms?: number | null;
}

export interface LLMConfigResponse {
  configured: boolean;
  base_url: string;
  model: string;
  persistence: string;
}
