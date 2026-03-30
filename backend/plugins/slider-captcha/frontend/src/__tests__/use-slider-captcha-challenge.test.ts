import { ref } from "vue";

import { describe, expect, it, vi } from "vitest";

import { useSliderCaptchaChallenge } from "../use-slider-captcha-challenge";

vi.mock("../render-slider-assets", () => ({
  renderSliderAssets: vi.fn().mockResolvedValue(42),
}));

function createCanvasRef() {
  return ref({
    getContext: () => ({
      clearRect: vi.fn(),
      drawImage: vi.fn(),
      getImageData: vi.fn(),
    }),
    height: 0,
    width: 0,
  } as unknown as HTMLCanvasElement);
}

function createOptions() {
  return {
    action: () => "login",
    boardCanvasRef: createCanvasRef(),
    difficulty: () => "medium" as const,
    dragX: ref(0),
    endpoint: () => "admin",
    getScaleRatio: () => 1,
    modalVisible: ref(true),
    pieceCanvasRef: createCanvasRef(),
    releaseDrag: vi.fn(),
    solved: ref(false),
    solvedOffset: ref<null | number>(null),
    syncDragAfterResize: vi.fn(),
    updateDisplayWidth: vi.fn(),
    updateModalPosition: vi.fn(),
  };
}

describe("use-slider-captcha-challenge", () => {
  it("loads challenge and forwards difficulty", async () => {
    const post = vi.fn().mockResolvedValue({
      challenge_id: "challenge-1",
      payload: {
        board_image: "data:image/png;base64,board",
        canvas_height: 180,
        canvas_width: 320,
        piece_height: 48,
        piece_image: "data:image/png;base64,piece",
        piece_top: 32,
        piece_width: 48,
        tolerance_px: 6,
      },
    });

    const state = useSliderCaptchaChallenge(() => ({ post }), createOptions());

    await state.loadChallenge();

    expect(post).toHaveBeenCalledWith("/api/public/captcha/challenge", {
      action: "login",
      difficulty: "medium",
      endpoint: "admin",
      provider_code: "slider",
    });
    expect(state.challengeId.value).toBe("challenge-1");
    expect(state.detectedTargetLeft.value).toBe(42);
    expect(state.statusKey.value).toBe("default");
  });

  it("marks retry when loading challenge fails", async () => {
    const state = useSliderCaptchaChallenge(
      () => ({
        post: vi
          .fn()
          .mockRejectedValue(new Error("request_client_unavailable")),
      }),
      createOptions(),
    );

    await expect(state.loadChallenge()).rejects.toThrow(
      "request_client_unavailable",
    );
    expect(state.statusKey.value).toBe("retry");
    expect(state.loading.value).toBe(false);
  });
});
