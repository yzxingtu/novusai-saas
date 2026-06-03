import { nextTick, ref } from "vue";

import { renderCaptchaToCanvas } from "./slider-captcha-canvas-renderer";

import type {
  SliderCaptchaRequestClient,
  SliderCaptchaStatusKey,
  SliderChallengePayload,
  SliderChallengeResponsePayload,
} from "./types";
import type { Ref } from "vue";

interface UseSliderCaptchaChallengeOptions {
  action: () => string;
  boardCanvasRef: Ref<HTMLCanvasElement | null>;
  difficulty: () => "easy" | "hard" | "medium";
  dragX: Ref<number>;
  endpoint: () => string;
  getScaleRatio: () => number;
  modalVisible: Ref<boolean>;
  pieceCanvasRef: Ref<HTMLCanvasElement | null>;
  releaseDrag: () => void;
  solved: Ref<boolean>;
  solvedOffset: Ref<null | number>;
  syncDragAfterResize: (previousScale: number) => void;
  updateDisplayWidth: () => void;
  updateModalPosition: () => void;
}

export function useSliderCaptchaChallenge(
  requestClient: () => SliderCaptchaRequestClient | undefined,
  options: UseSliderCaptchaChallengeOptions,
) {
  const challengeId = ref("");
  const challenge = ref<null | SliderChallengePayload>(null);
  const loading = ref(false);
  const statusKey = ref<SliderCaptchaStatusKey>("default");
  const detectedTargetLeft = ref<null | number>(null);

  let challengeRequestToken = 0;
  let renderToken = 0;

  function resetChallengeState(): void {
    options.releaseDrag();
    challengeRequestToken += 1;
    renderToken += 1;
    detectedTargetLeft.value = null;
    loading.value = false;
    challengeId.value = "";
    challenge.value = null;
    options.dragX.value = 0;
    options.solved.value = false;
    options.solvedOffset.value = null;
    statusKey.value = "default";
  }

  async function renderChallenge(): Promise<void> {
    const payload = challenge.value;
    if (!payload) {
      return;
    }

    const currentToken = ++renderToken;
    const targetLeft = await renderCaptchaToCanvas(payload, {
      boardCanvasRef: options.boardCanvasRef,
      pieceCanvasRef: options.pieceCanvasRef,
    });
    if (currentToken !== renderToken) {
      return;
    }
    detectedTargetLeft.value = targetLeft;
  }

  async function loadChallenge(): Promise<void> {
    const currentRequestToken = ++challengeRequestToken;
    options.releaseDrag();
    loading.value = true;
    options.solved.value = false;
    options.solvedOffset.value = null;
    options.dragX.value = 0;
    statusKey.value = "loading";

    try {
      const client = requestClient();
      if (!client) {
        throw new Error("request_client_unavailable");
      }

      const result = await client.post<SliderChallengeResponsePayload>(
        "/api/public/captcha/challenge",
        {
          action: options.action(),
          difficulty: options.difficulty(),
          endpoint: options.endpoint(),
          provider_code: "slider",
        },
      );
      if (!result?.payload) {
        throw new Error("challenge_request_failed");
      }
      if (currentRequestToken !== challengeRequestToken) {
        return;
      }

      challengeId.value = result.challenge_id;
      challenge.value = result.payload;
      statusKey.value = "default";
      await nextTick();
      options.updateDisplayWidth();
      await renderChallenge();
      if (options.modalVisible.value) {
        await nextTick();
        options.updateModalPosition();
      }
    } catch (error) {
      if (currentRequestToken !== challengeRequestToken) {
        return;
      }
      statusKey.value = "retry";
      throw error;
    } finally {
      if (currentRequestToken === challengeRequestToken) {
        loading.value = false;
      }
    }
  }

  async function rerenderExistingChallenge(): Promise<void> {
    const previousScale = options.getScaleRatio();
    await nextTick();
    options.updateDisplayWidth();
    options.syncDragAfterResize(previousScale);
    if (!challenge.value) {
      return;
    }
    await renderChallenge();
    if (options.modalVisible.value) {
      await nextTick();
      options.updateModalPosition();
    }
  }

  return {
    challenge,
    challengeId,
    detectedTargetLeft,
    loadChallenge,
    loading,
    renderChallenge,
    rerenderExistingChallenge,
    resetChallengeState,
    statusKey,
  };
}
