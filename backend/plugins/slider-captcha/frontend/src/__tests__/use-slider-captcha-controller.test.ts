// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import { createApp, defineComponent, h, nextTick } from "vue";

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SliderCaptchaStatusKey } from "../types";

import { useSliderCaptchaController } from "../use-slider-captcha-controller";

const mockRefs = vi.hoisted(() => {
  const stateMachine = {
    clearRetryTimer: vi.fn(),
    clearSuccessCloseTimer: vi.fn(),
    completeAttempt: vi.fn(),
    dispose: vi.fn(),
    getSolvedResult: vi.fn(() => null),
    prepareInteraction: vi.fn(),
    resetFailCounter: vi.fn(),
  };

  return {
    bindWindowEvents: vi.fn(() => vi.fn()),
    boardStyle: { value: { height: "180px", width: "320px" } },
    challenge: { value: null as null | Record<string, unknown> },
    challengeId: { value: "" },
    detectedTargetLeft: { value: null as null | number },
    handleTravelMax: { value: 200 },
    handleWidth: { value: 48 },
    handleX: { value: 30 },
    loadChallenge: vi.fn().mockResolvedValue(undefined),
    loading: { value: false },
    modalPanelStyle: {
      value: {
        "--panel-caret-left": "48px",
        left: "12px",
        top: "12px",
        width: "360px",
      },
    },
    pieceStyle: {
      value: {
        height: "48px",
        left: "0px",
        top: "24px",
        width: "48px",
      },
    },
    rerenderExistingChallenge: vi.fn().mockResolvedValue(undefined),
    resetChallengeState: vi.fn(),
    resolveKeyboardAction: vi.fn(() => null),
    scaleRatio: { value: 1 },
    setHandlePosition: vi.fn(),
    stateMachine,
    statusKey: { value: "default" as SliderCaptchaStatusKey },
    syncDragAfterResize: vi.fn(),
    updateDisplayWidth: vi.fn(),
    updateModalPosition: vi.fn(),
  };
});

vi.mock("../slider-captcha-a11y", () => ({
  bindSliderCaptchaWindowEvents: mockRefs.bindWindowEvents,
  resolveSliderThumbKeyboardAction: mockRefs.resolveKeyboardAction,
}));

vi.mock("../slider-captcha-state-machine", () => ({
  createSliderCaptchaStateMachine: () => mockRefs.stateMachine,
}));

vi.mock("../use-slider-captcha-challenge", () => ({
  useSliderCaptchaChallenge: () => ({
    challenge: mockRefs.challenge,
    challengeId: mockRefs.challengeId,
    detectedTargetLeft: mockRefs.detectedTargetLeft,
    loadChallenge: mockRefs.loadChallenge,
    loading: mockRefs.loading,
    rerenderExistingChallenge: mockRefs.rerenderExistingChallenge,
    resetChallengeState: mockRefs.resetChallengeState,
    statusKey: mockRefs.statusKey,
  }),
}));

vi.mock("../use-slider-captcha-layout", () => ({
  useSliderCaptchaLayout: () => ({
    boardStyle: mockRefs.boardStyle,
    handleTravelMax: mockRefs.handleTravelMax,
    handleWidth: mockRefs.handleWidth,
    handleX: mockRefs.handleX,
    modalPanelStyle: mockRefs.modalPanelStyle,
    pieceStyle: mockRefs.pieceStyle,
    scaleRatio: mockRefs.scaleRatio,
    setHandlePosition: mockRefs.setHandlePosition,
    syncDragAfterResize: mockRefs.syncDragAfterResize,
    updateDisplayWidth: mockRefs.updateDisplayWidth,
    updateModalPosition: mockRefs.updateModalPosition,
  }),
}));

function createHarness(disabled = false) {
  let controller: null | ReturnType<typeof useSliderCaptchaController> = null;
  const host = document.createElement("div");
  document.body.append(host);

  const app = createApp(
    defineComponent({
      setup() {
        controller = useSliderCaptchaController({
          action: () => "login",
          difficulty: () => "medium",
          disabled: () => disabled,
          endpoint: () => "admin",
          onError: vi.fn(),
          onVerified: vi.fn(),
        });
        return () => h("div");
      },
    }),
  );

  app.mount(host);

  return {
    app,
    controller: controller!,
    unmount() {
      app.unmount();
      host.remove();
    },
  };
}

async function flushMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("use-slider-captcha-controller", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockRefs.bindWindowEvents.mockReturnValue(vi.fn());
    mockRefs.challenge.value = null;
    mockRefs.challengeId.value = "";
    mockRefs.detectedTargetLeft.value = null;
    mockRefs.handleTravelMax.value = 200;
    mockRefs.handleWidth.value = 48;
    mockRefs.handleX.value = 30;
    mockRefs.loading.value = false;
    mockRefs.loadChallenge.mockResolvedValue(undefined);
    mockRefs.rerenderExistingChallenge.mockResolvedValue(undefined);
    mockRefs.resolveKeyboardAction.mockReturnValue(null);
    mockRefs.statusKey.value = "default";
    mockRefs.stateMachine.getSolvedResult.mockReturnValue(null);
  });

  it("opens the modal and loads a challenge when no solved result exists", async () => {
    const harness = createHarness();

    expect(harness.controller.getResult()).toBeNull();

    await nextTick();
    await flushMicrotasks();

    expect(harness.controller.modalVisible.value).toBe(true);
    expect(mockRefs.updateDisplayWidth).toHaveBeenCalledTimes(1);
    expect(mockRefs.updateModalPosition).toHaveBeenCalledTimes(1);
    expect(mockRefs.loadChallenge).toHaveBeenCalledTimes(1);

    harness.unmount();
  });

  it("routes keyboard increase interactions through the extracted orchestration seam", () => {
    mockRefs.challenge.value = {
      canvas_height: 180,
      canvas_width: 320,
      piece_height: 48,
      piece_top: 24,
      piece_width: 48,
      tolerance_px: 6,
    };
    mockRefs.resolveKeyboardAction.mockReturnValue("increase");

    const harness = createHarness();
    const event = {
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent;

    harness.controller.handleThumbKeydown(event);

    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    expect(mockRefs.stateMachine.prepareInteraction).toHaveBeenCalledTimes(1);
    expect(mockRefs.setHandlePosition).toHaveBeenCalledWith(50);

    harness.unmount();
  });

  it("disposes window orchestration and challenge state on unmount", () => {
    const unbind = vi.fn();
    mockRefs.bindWindowEvents.mockReturnValue(unbind);

    const harness = createHarness();

    harness.unmount();

    expect(mockRefs.stateMachine.dispose).toHaveBeenCalledTimes(1);
    expect(mockRefs.resetChallengeState).toHaveBeenCalledTimes(1);
    expect(unbind).toHaveBeenCalledTimes(1);
  });
});
