import { computed, type Ref } from "vue";

import { SLIDER_CAPTCHA_LOCALE_PREFIX } from "./slider-captcha-shared";

import type { SliderCaptchaStatusKey, SliderChallengePayload } from "./types";

const FALLBACK_TEXT = {
  modalSubtitle:
    "Drag the slider so the puzzle piece returns to the missing slot.",
  modalTipDefault:
    "Align the puzzle piece and sign-in will continue automatically.",
  modalTipRetry: "The piece is not aligned. Please drag again.",
  modalTipSuccess: "Verification succeeded. Continuing sign-in...",
  modal: {
    close: "Close dialog",
  },
  modalTitle: "Complete security verification",
  status: {
    default: "Drag the slider to verify",
    loading: "Loading challenge...",
    refresh: "Refresh",
    retry: "Try again",
    success: "Verified",
  },
  track: {
    default: "Drag right to complete verification",
    loading: "Loading challenge...",
    retry: "Drag right to try again",
    success: "Verification completed",
  },
  trigger: {
    action: {
      default: "Verify",
      retry: "Retry",
      success: "Verified",
    },
    title: {
      default: "Complete security verification",
      retry: "Verification failed, please retry",
      success: "Security verification completed",
    },
  },
} as const;

type UseSliderCaptchaCopyOptions = {
  challenge: Readonly<Ref<null | SliderChallengePayload>>;
  dragging: Readonly<Ref<boolean>>;
  handleX: Readonly<Ref<number>>;
  loading: Readonly<Ref<boolean>>;
  solved: Readonly<Ref<boolean>>;
  statusKey: Readonly<Ref<SliderCaptchaStatusKey>>;
  translate: (key: string) => string | undefined;
};

export function useSliderCaptchaCopy(options: UseSliderCaptchaCopyOptions) {
  function tLocal(path: string): string {
    const fullKey = `${SLIDER_CAPTCHA_LOCALE_PREFIX}.${path}`;
    const translated = options.translate(fullKey);
    if (!translated || translated === fullKey) {
      const segments = path.split(".");
      let current: unknown = FALLBACK_TEXT;
      for (const segment of segments) {
        if (!current || typeof current !== "object") {
          return fullKey;
        }
        current = (current as Record<string, unknown>)[segment];
      }
      return typeof current === "string" ? current : fullKey;
    }
    return translated;
  }

  const triggerTitle = computed(() => {
    if (options.solved.value) {
      return tLocal("trigger.title.success");
    }
    if (options.statusKey.value === "retry") {
      return tLocal("trigger.title.retry");
    }
    if (options.loading.value) {
      return tLocal("status.loading");
    }
    return tLocal("trigger.title.default");
  });

  const triggerActionLabel = computed(() => {
    if (options.solved.value) {
      return tLocal("trigger.action.success");
    }
    if (options.statusKey.value === "retry") {
      return tLocal("trigger.action.retry");
    }
    return tLocal("trigger.action.default");
  });

  const modalStatusText = computed(() =>
    tLocal(`status.${options.statusKey.value}`),
  );

  const modalTipText = computed(() => {
    if (options.solved.value) {
      return tLocal("modalTipSuccess");
    }
    if (options.statusKey.value === "retry") {
      return tLocal("modalTipRetry");
    }
    return tLocal("modalTipDefault");
  });

  const sliderTrackText = computed(() => {
    if (options.loading.value) {
      return tLocal("track.loading");
    }
    if (options.solved.value) {
      return tLocal("track.success");
    }
    if (options.statusKey.value === "retry") {
      return tLocal("track.retry");
    }
    return tLocal("track.default");
  });

  const showTrackCopy = computed(() => {
    return (
      Boolean(options.challenge.value) &&
      !options.loading.value &&
      !options.solved.value &&
      options.statusKey.value === "default" &&
      !options.dragging.value &&
      options.handleX.value <= 1
    );
  });

  return {
    modalStatusText,
    modalTipText,
    showTrackCopy,
    sliderTrackText,
    tLocal,
    triggerActionLabel,
    triggerTitle,
  };
}
