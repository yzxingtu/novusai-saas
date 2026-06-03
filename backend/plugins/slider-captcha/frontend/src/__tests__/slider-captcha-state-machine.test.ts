import { ref } from "vue";

import { afterEach, describe, expect, it, vi } from "vitest";

import { createSliderCaptchaStateMachine } from "../slider-captcha-state-machine";

import type { SliderCaptchaStatusKey, SliderChallengePayload } from "../types";

function createChallenge(): SliderChallengePayload {
  return {
    canvas_height: 180,
    canvas_width: 320,
    piece_height: 48,
    piece_top: 36,
    piece_width: 48,
    tolerance_px: 6,
  };
}

function createStateMachineContext() {
  const challenge = ref<SliderChallengePayload | null>(createChallenge());
  const challengeId = ref("challenge-1");
  const detectedTargetLeft = ref<number | null>(120);
  const dragX = ref(239);
  const modalVisible = ref(true);
  const solved = ref(false);
  const solvedOffset = ref<number | null>(null);
  const statusKey = ref<SliderCaptchaStatusKey>("default");
  const onRefresh = vi.fn();
  const onVerified = vi.fn();

  const stateMachine = createSliderCaptchaStateMachine({
    challenge,
    challengeId,
    detectedTargetLeft,
    dragX,
    modalVisible,
    onRefresh,
    onVerified,
    scaleRatio: () => 2,
    solved,
    solvedOffset,
    statusKey,
  });

  return {
    challenge,
    detectedTargetLeft,
    dragX,
    modalVisible,
    onRefresh,
    onVerified,
    solved,
    solvedOffset,
    stateMachine,
    statusKey,
  };
}

describe("slider-captcha-state-machine", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("snaps a successful attempt, emits the solved payload, and closes later", () => {
    vi.useFakeTimers();
    const context = createStateMachineContext();

    context.stateMachine.completeAttempt();

    expect(context.dragX.value).toBe(240);
    expect(context.solved.value).toBe(true);
    expect(context.solvedOffset.value).toBe(120);
    expect(context.statusKey.value).toBe("success");
    expect(context.onVerified).toHaveBeenCalledWith({
      captchaCode: "120",
      challengeId: "challenge-1",
      provider: "slider",
    });
    expect(context.stateMachine.getSolvedResult()).toEqual({
      captchaCode: "120",
      challengeId: "challenge-1",
      provider: "slider",
    });

    vi.advanceTimersByTime(420);

    expect(context.modalVisible.value).toBe(false);
  });

  it("resets drag state after a single local retry window", () => {
    vi.useFakeTimers();
    const context = createStateMachineContext();
    context.dragX.value = 48;

    context.stateMachine.completeAttempt();

    expect(context.statusKey.value).toBe("retry");
    expect(context.solved.value).toBe(false);
    expect(context.solvedOffset.value).toBeNull();
    expect(context.onRefresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(419);
    expect(context.dragX.value).toBe(48);
    expect(context.statusKey.value).toBe("retry");

    vi.advanceTimersByTime(1);
    expect(context.dragX.value).toBe(0);
    expect(context.statusKey.value).toBe("default");
  });

  it("refreshes the challenge after the third consecutive failure", () => {
    vi.useFakeTimers();
    const context = createStateMachineContext();

    for (let attempt = 0; attempt < 2; attempt += 1) {
      context.dragX.value = 24;
      context.stateMachine.completeAttempt();
      vi.advanceTimersByTime(420);
    }

    context.dragX.value = 24;
    context.stateMachine.completeAttempt();

    expect(context.statusKey.value).toBe("retry");
    expect(context.onRefresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(599);
    expect(context.onRefresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(context.onRefresh).toHaveBeenCalledTimes(1);
  });
});
