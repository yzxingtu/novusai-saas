export interface AgentRoutingState {
  enabled: boolean;
  maxTier: string | undefined;
  visionModelId: number | undefined;
  audioModelId: number | undefined;
  videoModelId: number | undefined;
  longContextModelId: number | undefined;
  longContextThreshold: number;
}

export interface AgentRoutingSourceModel {
  id: number;
  name: string;
  provider_name: null | string;
  supports_audio?: boolean | null;
  supports_video?: boolean | null;
  supports_vision?: boolean | null;
  max_output_tokens?: null | number;
}

export interface AgentRoutingOption<T extends number | string> {
  label: string;
  value: T;
}

export interface AgentRoutingModelOptions {
  audioModelOptions: AgentRoutingOption<number>[];
  chatModelMaxOutputTokens: Record<number, number | undefined>;
  chatModelOptions: AgentRoutingOption<number>[];
  videoModelOptions: AgentRoutingOption<number>[];
  visionModelOptions: AgentRoutingOption<number>[];
}

export function createAgentRoutingState(): AgentRoutingState {
  return {
    enabled: false,
    maxTier: undefined,
    visionModelId: undefined,
    audioModelId: undefined,
    videoModelId: undefined,
    longContextModelId: undefined,
    longContextThreshold: 32_000,
  };
}

export function createEmptyAgentRoutingModelOptions(): AgentRoutingModelOptions {
  return {
    audioModelOptions: [],
    chatModelMaxOutputTokens: {},
    chatModelOptions: [],
    videoModelOptions: [],
    visionModelOptions: [],
  };
}

export function applyAgentRoutingConfig(
  state: AgentRoutingState,
  config: null | Record<string, unknown> | undefined,
): void {
  const routingConfig = config ?? {};
  state.enabled = Boolean(routingConfig.enable_routing);
  state.maxTier = (routingConfig.max_tier as string | undefined) ?? undefined;
  state.visionModelId =
    (routingConfig.vision_model_id as number | undefined) ?? undefined;
  state.audioModelId =
    (routingConfig.audio_model_id as number | undefined) ?? undefined;
  state.videoModelId =
    (routingConfig.video_model_id as number | undefined) ?? undefined;
  state.longContextModelId =
    (routingConfig.long_context_model_id as number | undefined) ?? undefined;
  state.longContextThreshold =
    (routingConfig.long_context_threshold as number | undefined) ?? 32_000;
}

export function buildAgentRoutingPayload(
  state: AgentRoutingState,
): Record<string, boolean | null | number | string> {
  return {
    enable_routing: state.enabled,
    max_tier: state.maxTier || null,
    vision_model_id: state.visionModelId ?? null,
    audio_model_id: state.audioModelId ?? null,
    video_model_id: state.videoModelId ?? null,
    long_context_model_id: state.longContextModelId ?? null,
    long_context_threshold: state.longContextThreshold,
  };
}

export function buildAgentRoutingModelOptions(
  models: AgentRoutingSourceModel[],
): AgentRoutingModelOptions {
  const toOption = (
    model: AgentRoutingSourceModel,
  ): AgentRoutingOption<number> => ({
    label: `${model.name} (${model.provider_name || '-'})`,
    value: model.id,
  });

  return {
    audioModelOptions: models
      .filter((model) => Boolean(model.supports_audio))
      .map((model) => toOption(model)),
    chatModelMaxOutputTokens: Object.fromEntries(
      models.map((model) => [model.id, model.max_output_tokens ?? undefined]),
    ),
    chatModelOptions: models.map((model) => toOption(model)),
    videoModelOptions: models
      .filter((model) => Boolean(model.supports_video))
      .map((model) => toOption(model)),
    visionModelOptions: models
      .filter((model) => Boolean(model.supports_vision))
      .map((model) => toOption(model)),
  };
}
