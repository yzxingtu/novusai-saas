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

function createChallengeResponse(challengeId = "challenge-1") {
  return {
    challenge_id: challengeId,
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
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });

  return {
    promise,
    reject,
    resolve,
  };
}

describe("use-slider-captcha-challenge", () => {
  it("loads challenge and forwards difficulty", async () => {
    const post = vi.fn().mockResolvedValue(createChallengeResponse());

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

  it("ignores stale challenge responses when a newer load wins", async () => {
    const firstRequest = createDeferred<
      ReturnType<typeof createChallengeResponse>
    >();
    const secondRequest = createDeferred<
      ReturnType<typeof createChallengeResponse>
    >();
    const post = vi
      .fn()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise);
    const options = createOptions();

    const state = useSliderCaptchaChallenge(() => ({ post }), options);

    const firstLoad = state.loadChallenge();
    const secondLoad = state.loadChallenge();

    secondRequest.resolve(createChallengeResponse("challenge-2"));
    await secondLoad;

    firstRequest.resolve(createChallengeResponse("challenge-1"));
    await firstLoad;

    expect(state.challengeId.value).toBe("challenge-2");
    expect(options.updateDisplayWidth).toHaveBeenCalledTimes(1);
    expect(options.updateModalPosition).toHaveBeenCalledTimes(1);
    expect(state.statusKey.value).toBe("default");
    expect(state.loading.value).toBe(false);
  });

  it("rerenders with the previous scale ratio and updates modal position when visible", async () => {
    const options = createOptions();
    const post = vi.fn().mockResolvedValue(createChallengeResponse());

    const state = useSliderCaptchaChallenge(() => ({ post }), options);

    await state.loadChallenge();
    options.getScaleRatio = vi.fn(() => 0.75);

    await state.rerenderExistingChallenge();

    expect(options.syncDragAfterResize).toHaveBeenCalledWith(0.75);
    expect(options.updateDisplayWidth).toHaveBeenCalledTimes(2);
    expect(options.updateModalPosition).toHaveBeenCalledTimes(2);
    expect(state.detectedTargetLeft.value).toBe(42);
  });
});
