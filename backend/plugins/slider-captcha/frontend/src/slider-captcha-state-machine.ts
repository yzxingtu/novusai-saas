import type {
  SliderCaptchaResult,
  SliderCaptchaStatusKey,
  SliderChallengePayload,
} from "./types";
import type { Ref } from "vue";

const MAX_LOCAL_RETRIES = 3;
const PROVIDER_CODE = "slider";

interface SliderCaptchaStateMachineOptions {
  challenge: Ref<null | SliderChallengePayload>;
  challengeId: Ref<string>;
  detectedTargetLeft: Ref<null | number>;
  dragX: Ref<number>;
  modalVisible: Ref<boolean>;
  scaleRatio: () => number;
  solved: Ref<boolean>;
  solvedOffset: Ref<null | number>;
  statusKey: Ref<SliderCaptchaStatusKey>;
  onRefresh: () => void;
  onVerified: (result: SliderCaptchaResult) => void;
}

export function createSliderCaptchaStateMachine(
  options: SliderCaptchaStateMachineOptions,
) {
  let retryTimer: null | number = null;
  let successCloseTimer: null | number = null;
  let consecutiveFailCount = 0;

  function clearRetryTimer(): void {
    if (retryTimer !== null) {
      window.clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

  function clearSuccessCloseTimer(): void {
    if (successCloseTimer !== null) {
      window.clearTimeout(successCloseTimer);
      successCloseTimer = null;
    }
  }

  function resetFailCounter(): void {
    consecutiveFailCount = 0;
  }

  function prepareInteraction(): void {
    clearRetryTimer();
    clearSuccessCloseTimer();
    options.statusKey.value = "default";
  }

  function resetDragAfterRetry(): void {
    clearRetryTimer();
    retryTimer = window.setTimeout(() => {
      options.dragX.value = 0;
      options.statusKey.value = "default";
      retryTimer = null;
    }, 420);
  }

  function handleAttemptFail(): void {
    consecutiveFailCount += 1;
    options.solved.value = false;
    options.solvedOffset.value = null;

    if (consecutiveFailCount >= MAX_LOCAL_RETRIES) {
      options.statusKey.value = "retry";
      clearRetryTimer();
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        consecutiveFailCount = 0;
        options.onRefresh();
      }, 600);
      return;
    }

    options.statusKey.value = "retry";
    resetDragAfterRetry();
  }

  function completeAttempt(): void {
    const challenge = options.challenge.value;
    if (!challenge) {
      return;
    }

    const expectedLeft = options.detectedTargetLeft.value;
    const actualOffset = Math.round(options.dragX.value / options.scaleRatio());
    if (expectedLeft === null) {
      handleAttemptFail();
      return;
    }

    if (Math.abs(actualOffset - expectedLeft) <= challenge.tolerance_px) {
      consecutiveFailCount = 0;
      options.dragX.value = expectedLeft * options.scaleRatio();
      options.solved.value = true;
      options.solvedOffset.value = actualOffset;
      options.statusKey.value = "success";
      options.onVerified({
        captchaCode: String(actualOffset),
        challengeId: options.challengeId.value,
        provider: PROVIDER_CODE,
      });
      clearSuccessCloseTimer();
      successCloseTimer = window.setTimeout(() => {
        options.modalVisible.value = false;
        successCloseTimer = null;
      }, 420);
      return;
    }

    handleAttemptFail();
  }

  function getSolvedResult(): null | SliderCaptchaResult {
    if (
      !options.solved.value ||
      !options.challengeId.value ||
      options.solvedOffset.value == null
    ) {
      return null;
    }
    return {
      captchaCode: String(options.solvedOffset.value),
      challengeId: options.challengeId.value,
      provider: PROVIDER_CODE,
    };
  }

  function dispose(): void {
    clearRetryTimer();
    clearSuccessCloseTimer();
    consecutiveFailCount = 0;
  }

  return {
    clearRetryTimer,
    clearSuccessCloseTimer,
    completeAttempt,
    dispose,
    getSolvedResult,
    prepareInteraction,
    resetFailCounter,
  };
}

