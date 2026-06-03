import { describe, expect, it } from 'vitest';

import {
  applyAgentRoutingConfig,
  buildAgentRoutingModelOptions,
  buildAgentRoutingPayload,
  createAgentRoutingState,
} from '../use-agent-routing';

describe('use-agent-routing helpers', () => {
  it('applies routing config with sane defaults', () => {
    const state = createAgentRoutingState();

    applyAgentRoutingConfig(state, {
      enable_routing: true,
      max_tier: 'premium',
      vision_model_id: 11,
      long_context_threshold: 64_000,
    });

    expect(state).toMatchObject({
      enabled: true,
      maxTier: 'premium',
      visionModelId: 11,
      audioModelId: undefined,
      longContextThreshold: 64_000,
    });
  });

  it('builds routing payload with nullable ids', () => {
    const state = createAgentRoutingState();
    state.enabled = true;
    state.maxTier = 'fast';
    state.audioModelId = 7;

    expect(buildAgentRoutingPayload(state)).toEqual({
      enable_routing: true,
      max_tier: 'fast',
      vision_model_id: null,
      audio_model_id: 7,
      video_model_id: null,
      long_context_model_id: null,
      long_context_threshold: 32_000,
    });
  });

  it('maps model capability options and max output tokens', () => {
    const options = buildAgentRoutingModelOptions([
      {
        id: 1,
        name: 'Chat One',
        provider_name: 'OpenAI',
        supports_audio: true,
        supports_vision: false,
        supports_video: true,
        max_output_tokens: 4096,
      },
      {
        id: 2,
        name: 'Chat Two',
        provider_name: null,
        supports_audio: false,
        supports_vision: true,
        supports_video: false,
        max_output_tokens: null,
      },
    ]);

    expect(options.chatModelOptions).toHaveLength(2);
    expect(options.audioModelOptions.map((item) => item.value)).toEqual([1]);
    expect(options.videoModelOptions.map((item) => item.value)).toEqual([1]);
    expect(options.visionModelOptions.map((item) => item.value)).toEqual([2]);
    expect(options.chatModelMaxOutputTokens).toEqual({
      1: 4096,
      2: undefined,
    });
  });
});
