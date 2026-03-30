<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import type { SliderCaptchaResult, SliderCaptchaSharedAPI } from "./types";
import { useSliderCaptchaChallenge } from "./use-slider-captcha-challenge";

const PROVIDER_CODE = "slider";
const LOCALE_PREFIX = "plugin.slider-captcha";
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

const props = withDefaults(
  defineProps<{
    action?: string;
    disabled?: boolean;
    difficulty?: "easy" | "hard" | "medium";
    endpoint: string;
  }>(),
  {
    action: "login",
    disabled: false,
    difficulty: "medium",
  },
);

const emit = defineEmits<{
  (e: "error", error: Error): void;
  (e: "verified", result: SliderCaptchaResult): void;
}>();

const triggerButtonRef = ref<HTMLElement | null>(null);
const modalPanelRef = ref<HTMLElement | null>(null);
const boardHostRef = ref<HTMLElement | null>(null);
const boardCanvasRef = ref<HTMLCanvasElement | null>(null);
const pieceCanvasRef = ref<HTMLCanvasElement | null>(null);

const dragX = ref(0);
const solved = ref(false);
const solvedOffset = ref<number | null>(null);
const displayWidth = ref(320);
const dragging = ref(false);
const modalVisible = ref(false);
const modalPlacement = ref<"bottom" | "center" | "top">("top");
const modalPosition = ref({
  caretLeft: 48,
  left: 12,
  top: 12,
  width: 360,
});

const MAX_LOCAL_RETRIES = 3;

let pointerId: null | number = null;
let pointerStartX = 0;
let pointerStartHandleX = 0;
let retryTimer: null | number = null;
let successCloseTimer: null | number = null;
let consecutiveFailCount = 0;

function getShared(): SliderCaptchaSharedAPI | undefined {
  return (window as unknown as { NovusPluginShared?: SliderCaptchaSharedAPI })
    .NovusPluginShared;
}

const {
  challenge,
  challengeId,
  detectedTargetLeft,
  loadChallenge,
  loading,
  rerenderExistingChallenge,
  resetChallengeState,
  statusKey,
} = useSliderCaptchaChallenge(() => getShared()?.requestClient, {
  action: () => props.action,
  boardCanvasRef,
  difficulty: () => props.difficulty,
  dragX,
  endpoint: () => props.endpoint,
  getScaleRatio: () => scaleRatio.value,
  modalVisible,
  pieceCanvasRef,
  releaseDrag,
  solved,
  solvedOffset,
  syncDragAfterResize,
  updateDisplayWidth,
  updateModalPosition,
});

function tLocal(path: string): string {
  const fullKey = `${LOCALE_PREFIX}.${path}`;
  const translated = getShared()?.$t?.(fullKey);
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

const boardWidth = computed(() => {
  if (!challenge.value) {
    return 320;
  }
  return Math.min(displayWidth.value, challenge.value.canvas_width);
});

const scaleRatio = computed(() => {
  if (!challenge.value) {
    return 1;
  }
  return boardWidth.value / challenge.value.canvas_width;
});

const boardHeight = computed(() => {
  if (!challenge.value) {
    return 180;
  }
  return challenge.value.canvas_height * scaleRatio.value;
});

const pieceLength = computed(() => {
  if (!challenge.value) {
    return 0;
  }
  return challenge.value.piece_width;
});

const pieceTravelMax = computed(() => {
  if (!challenge.value) {
    return 0;
  }
  return Math.max(0, boardWidth.value - pieceLength.value * scaleRatio.value);
});

const handleWidth = computed(() => {
  return Math.max(42, Math.min(48, boardWidth.value * 0.15));
});

const handleTravelMax = computed(() => {
  return Math.max(0, boardWidth.value - handleWidth.value);
});

const handleX = computed(() => {
  if (!pieceTravelMax.value || !handleTravelMax.value) {
    return 0;
  }
  return (dragX.value / pieceTravelMax.value) * handleTravelMax.value;
});

const pieceStyle = computed(() => {
  if (!challenge.value) {
    return {
      height: "0px",
      left: "0px",
      top: "0px",
      width: "0px",
    };
  }

  const pieceTop = challenge.value.piece_top * scaleRatio.value;
  const pieceHeight = challenge.value.piece_height * scaleRatio.value;
  const pieceWidth = challenge.value.piece_width * scaleRatio.value;

  return {
    height: `${pieceHeight}px`,
    left: `${dragX.value}px`,
    top: `${pieceTop}px`,
    width: `${pieceWidth}px`,
  };
});

const boardStyle = computed(() => {
  return {
    height: `${boardHeight.value}px`,
    width: `${boardWidth.value}px`,
  };
});

const modalPanelStyle = computed(() => {
  return {
    "--panel-caret-left": `${modalPosition.value.caretLeft}px`,
    left: `${modalPosition.value.left}px`,
    top: `${modalPosition.value.top}px`,
    width: `${modalPosition.value.width}px`,
  } as Record<string, string>;
});

const triggerTitle = computed(() => {
  if (solved.value) {
    return tLocal("trigger.title.success");
  }
  if (statusKey.value === "retry") {
    return tLocal("trigger.title.retry");
  }
  if (loading.value) {
    return tLocal("status.loading");
  }
  return tLocal("trigger.title.default");
});

const triggerActionLabel = computed(() => {
  if (solved.value) {
    return tLocal("trigger.action.success");
  }
  if (statusKey.value === "retry") {
    return tLocal("trigger.action.retry");
  }
  return tLocal("trigger.action.default");
});

const modalStatusText = computed(() => tLocal(`status.${statusKey.value}`));

const modalTipText = computed(() => {
  if (solved.value) {
    return tLocal("modalTipSuccess");
  }
  if (statusKey.value === "retry") {
    return tLocal("modalTipRetry");
  }
  return tLocal("modalTipDefault");
});

const sliderTrackText = computed(() => {
  if (loading.value) {
    return tLocal("track.loading");
  }
  if (solved.value) {
    return tLocal("track.success");
  }
  if (statusKey.value === "retry") {
    return tLocal("track.retry");
  }
  return tLocal("track.default");
});

const showTrackCopy = computed(() => {
  return (
    Boolean(challenge.value) &&
    !loading.value &&
    !solved.value &&
    statusKey.value === "default" &&
    !dragging.value &&
    handleX.value <= 1
  );
});

const progressPercent = computed(() => {
  if (!handleTravelMax.value) {
    return solved.value ? 100 : 0;
  }
  return Math.round((handleX.value / handleTravelMax.value) * 100);
});

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

function updateDisplayWidth(): void {
  const width = boardHostRef.value?.clientWidth ?? 320;
  displayWidth.value = Math.max(280, Math.min(300, width));
}

function updateModalPosition(): void {
  const triggerEl = triggerButtonRef.value;
  if (!triggerEl) {
    return;
  }

  const rect = triggerEl.getBoundingClientRect();
  const viewportPadding = 12;
  const panelGap = 10;
  const preferredWidth = Math.max(312, Math.min(336, rect.width + 8));
  const width = Math.min(
    preferredWidth,
    Math.max(280, window.innerWidth - viewportPadding * 2),
  );
  const maxLeft = Math.max(
    viewportPadding,
    window.innerWidth - viewportPadding - width,
  );
  const left = Math.min(
    Math.max(viewportPadding, rect.left + rect.width / 2 - width / 2),
    maxLeft,
  );

  const panelHeight = modalPanelRef.value?.offsetHeight ?? 336;
  const topCandidate = rect.top - panelHeight - panelGap;
  const bottomCandidate = rect.bottom + panelGap;
  let placement: "bottom" | "center" | "top" = "top";
  let top = topCandidate;

  if (topCandidate < viewportPadding) {
    if (bottomCandidate + panelHeight <= window.innerHeight - viewportPadding) {
      placement = "bottom";
      top = bottomCandidate;
    } else {
      placement = "center";
      top = Math.max(
        viewportPadding,
        Math.round((window.innerHeight - panelHeight) / 2),
      );
    }
  }

  const maxTop = Math.max(
    viewportPadding,
    window.innerHeight - viewportPadding - panelHeight,
  );
  const caretLeft = Math.min(
    Math.max(30, rect.left + rect.width / 2 - left),
    width - 30,
  );

  modalPlacement.value = placement;
  modalPosition.value = {
    caretLeft: placement === "center" ? width / 2 : caretLeft,
    left:
      placement === "center"
        ? Math.min(
            Math.max(
              viewportPadding,
              Math.round((window.innerWidth - width) / 2),
            ),
            maxLeft,
          )
        : left,
    top: Math.min(Math.max(viewportPadding, top), maxTop),
    width,
  };
}

function setPieceLeft(pieceLeft: number): void {
  dragX.value = Math.min(
    pieceTravelMax.value,
    Math.max(0, pieceLeft * scaleRatio.value),
  );
}

function setHandlePosition(nextHandle: number): void {
  if (!handleTravelMax.value || !pieceTravelMax.value) {
    dragX.value = 0;
    return;
  }

  const clampedHandle = Math.max(
    0,
    Math.min(handleTravelMax.value, nextHandle),
  );
  dragX.value = (clampedHandle / handleTravelMax.value) * pieceTravelMax.value;
}

function syncDragAfterResize(previousScale: number): void {
  if (!challenge.value || previousScale <= 0) {
    return;
  }

  const pieceLeft = solved.value
    ? (solvedOffset.value ?? dragX.value / previousScale)
    : dragX.value / previousScale;

  setPieceLeft(pieceLeft);
}

function releaseDrag(): void {
  pointerId = null;
  dragging.value = false;
  window.removeEventListener("pointermove", handlePointerMove);
  window.removeEventListener("pointerup", handlePointerUp);
  window.removeEventListener("pointercancel", handlePointerUp);
}

function resetDragAfterRetry(): void {
  clearRetryTimer();
  retryTimer = window.setTimeout(() => {
    dragX.value = 0;
    statusKey.value = "default";
    retryTimer = null;
  }, 420);
}

function prepareInteraction(): void {
  clearRetryTimer();
  clearSuccessCloseTimer();
  statusKey.value = "default";
}

function handlePointerMove(event: PointerEvent): void {
  if (pointerId === null || props.disabled || !challenge.value) {
    return;
  }

  const deltaX = event.clientX - pointerStartX;
  const nextHandle = Math.max(
    0,
    Math.min(handleTravelMax.value, pointerStartHandleX + deltaX),
  );

  if (!handleTravelMax.value || !pieceTravelMax.value) {
    dragX.value = 0;
    return;
  }

  setHandlePosition(nextHandle);
}

function completeAttempt(): void {
  if (!challenge.value) {
    return;
  }

  const expectedLeft = detectedTargetLeft.value;
  const actualOffset = Math.round(dragX.value / scaleRatio.value);
  const tolerancePx = challenge.value.tolerance_px;
  if (expectedLeft === null) {
    handleAttemptFail();
    return;
  }

  if (Math.abs(actualOffset - expectedLeft) <= tolerancePx) {
    consecutiveFailCount = 0;
    dragX.value = expectedLeft * scaleRatio.value;
    solved.value = true;
    solvedOffset.value = actualOffset;
    statusKey.value = "success";
    emit("verified", {
      captchaCode: String(actualOffset),
      challengeId: challengeId.value,
      provider: PROVIDER_CODE,
    });
    clearSuccessCloseTimer();
    successCloseTimer = window.setTimeout(() => {
      modalVisible.value = false;
      successCloseTimer = null;
    }, 420);
    return;
  }

  handleAttemptFail();
}

function handleAttemptFail(): void {
  consecutiveFailCount += 1;
  solved.value = false;
  solvedOffset.value = null;

  if (consecutiveFailCount >= MAX_LOCAL_RETRIES) {
    statusKey.value = "retry";
    clearRetryTimer();
    retryTimer = window.setTimeout(() => {
      retryTimer = null;
      consecutiveFailCount = 0;
      refresh();
    }, 600);
    return;
  }

  statusKey.value = "retry";
  resetDragAfterRetry();
}

function handlePointerUp(): void {
  const hasActiveDrag = pointerId !== null;
  releaseDrag();
  if (!challenge.value || !hasActiveDrag) {
    return;
  }

  completeAttempt();
}

function handleThumbKeydown(event: KeyboardEvent): void {
  if (props.disabled || loading.value || !challenge.value || solved.value) {
    return;
  }

  const step = Math.max(12, Math.round(handleTravelMax.value / 10));

  switch (event.key) {
    case "ArrowLeft": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleX.value - step);
      return;
    }
    case "ArrowRight": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleX.value + step);
      return;
    }
    case "End": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleTravelMax.value);
      return;
    }
    case "Home": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(0);
      return;
    }
    case "Enter":
    case " ": {
      event.preventDefault();
      completeAttempt();
      return;
    }
    default: {
      return;
    }
  }
}

function startDrag(event: PointerEvent): void {
  if (props.disabled || loading.value || !challenge.value || solved.value) {
    return;
  }

  prepareInteraction();
  pointerId = event.pointerId;
  dragging.value = true;
  pointerStartX = event.clientX;
  pointerStartHandleX = handleX.value;
  window.addEventListener("pointermove", handlePointerMove);
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("pointercancel", handlePointerUp);
}

function closeModal(): void {
  clearSuccessCloseTimer();
  if (!modalVisible.value) {
    return;
  }
  if (solved.value) {
    releaseDrag();
    clearRetryTimer();
    modalVisible.value = false;
    return;
  }
  resetChallengeState();
  modalVisible.value = false;
}

function openModal(forceRefresh = false): void {
  if (props.disabled) {
    return;
  }

  clearSuccessCloseTimer();
  consecutiveFailCount = 0;
  if (forceRefresh) {
    if (modalVisible.value) {
      refresh();
      return;
    }
    resetChallengeState();
  }
  modalVisible.value = true;
}

function handleTriggerClick(): void {
  if (props.disabled || solved.value) {
    return;
  }
  openModal(statusKey.value === "retry" || !challenge.value);
}

function refresh(): void {
  consecutiveFailCount = 0;
  resetChallengeState();
  if (modalVisible.value) {
    void safeLoadChallenge();
  }
}

function getResult(): SliderCaptchaResult | null {
  if (!solved.value || !challengeId.value || solvedOffset.value == null) {
    openModal(statusKey.value === "retry" || !challenge.value);
    return null;
  }
  return {
    captchaCode: String(solvedOffset.value),
    challengeId: challengeId.value,
    provider: PROVIDER_CODE,
  };
}

defineExpose({
  getResult,
  refresh,
});

function handlePluginError(error: unknown): void {
  emit("error", error instanceof Error ? error : new Error(String(error)));
}

async function safeLoadChallenge(): Promise<void> {
  try {
    await loadChallenge();
  } catch (error) {
    handlePluginError(error);
  }
}

async function safeRerenderChallenge(): Promise<void> {
  try {
    await rerenderExistingChallenge();
  } catch (error) {
    statusKey.value = "retry";
    handlePluginError(error);
  }
}

function handleWindowKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && modalVisible.value) {
    closeModal();
  }
}

function handleWindowResize(): void {
  if (!modalVisible.value) {
    return;
  }
  void safeRerenderChallenge();
}

function handleWindowScroll(): void {
  if (modalVisible.value) {
    updateModalPosition();
  }
}

watch(
  () => [props.action, props.endpoint],
  () => {
    resetChallengeState();
    if (modalVisible.value) {
      void safeLoadChallenge();
    }
  },
);

watch(modalVisible, async (visible) => {
  if (!visible) {
    return;
  }
  await nextTick();
  updateDisplayWidth();
  updateModalPosition();
  if (!challenge.value) {
    void safeLoadChallenge();
    return;
  }
  await safeRerenderChallenge();
});

onMounted(() => {
  window.addEventListener("resize", handleWindowResize);
  window.addEventListener("scroll", handleWindowScroll, true);
  window.addEventListener("keydown", handleWindowKeydown);
});

onBeforeUnmount(() => {
  resetChallengeState();
  modalVisible.value = false;
  window.removeEventListener("resize", handleWindowResize);
  window.removeEventListener("scroll", handleWindowScroll, true);
  window.removeEventListener("keydown", handleWindowKeydown);
});
</script>

<template>
  <div class="slider-captcha-plugin">
    <button
      ref="triggerButtonRef"
      type="button"
      class="captcha-trigger"
      :class="{
        'is-loading': loading,
        'is-retry': statusKey === 'retry',
        'is-solved': solved,
      }"
      :data-state="statusKey"
      :aria-expanded="modalVisible"
      :disabled="props.disabled || solved"
      @click="handleTriggerClick"
    >
      <span class="trigger-icon" aria-hidden="true">
        <span class="trigger-icon-core"></span>
      </span>
      <span class="trigger-copy">
        <span class="trigger-title">{{ triggerTitle }}</span>
      </span>
      <span class="trigger-meta">
        <span class="trigger-action-text">{{ triggerActionLabel }}</span>
        <span class="trigger-arrow-icon" aria-hidden="true"></span>
      </span>
    </button>
  </div>

  <Teleport to="body">
    <Transition name="slider-captcha-fade">
      <div
        v-if="modalVisible"
        class="captcha-floating-layer"
        @click.self="closeModal"
      >
        <div
          ref="modalPanelRef"
          class="captcha-modal-panel"
          :data-placement="modalPlacement"
          :data-state="statusKey"
          :style="modalPanelStyle"
          role="dialog"
          aria-modal="true"
          :aria-label="tLocal('modalTitle')"
        >
          <span class="panel-caret" aria-hidden="true"></span>
          <div class="modal-header">
            <div class="modal-title-group">
              <h3 class="modal-title">{{ tLocal("modalTitle") }}</h3>
              <p class="modal-subtitle">{{ tLocal("modalSubtitle") }}</p>
            </div>
            <div class="modal-actions">
              <button
                class="modal-refresh"
                type="button"
                :disabled="props.disabled || loading"
                @click="refresh"
              >
                {{ tLocal("status.refresh") }}
              </button>
              <button
                type="button"
                class="modal-close-button"
                :aria-label="tLocal('modal.close')"
                :title="tLocal('modal.close')"
                @click="closeModal"
              >
                <span class="close-icon" aria-hidden="true"></span>
              </button>
            </div>
          </div>

          <div class="modal-stage">
            <div ref="boardHostRef" class="board-host">
              <div
                name="captcha"
                class="captcha-board"
                :class="{ 'is-solved': solved }"
                :style="boardStyle"
              >
                <canvas ref="boardCanvasRef" class="board-canvas"></canvas>
                <canvas
                  ref="pieceCanvasRef"
                  class="piece-canvas"
                  :class="{ 'is-dragging': dragging, 'is-solved': solved }"
                  :style="pieceStyle"
                ></canvas>

                <div v-if="!challenge && !loading" class="board-empty">
                  <span class="board-empty-title">{{ modalStatusText }}</span>
                </div>

                <div v-if="loading" class="board-loading">
                  <span class="loading-dot"></span>
                  <span>{{ tLocal("status.loading") }}</span>
                </div>
              </div>
            </div>

            <div class="captcha-slider">
              <div
                class="slider-track"
                :class="{ 'is-dragging': dragging }"
                :data-state="statusKey"
                :style="{ '--track-handle-width': `${handleWidth}px` }"
              >
                <div
                  class="track-fill"
                  :style="{ width: `${handleX + handleWidth}px` }"
                ></div>
                <div v-if="showTrackCopy" class="track-copy">
                  {{ tLocal("track.default") }}
                </div>
                <button
                  name="captcha-action"
                  type="button"
                  class="slider-thumb"
                  :class="{ 'is-dragging': dragging, 'is-solved': solved }"
                  :disabled="props.disabled || loading"
                  :style="{ left: `${handleX}px`, width: `${handleWidth}px` }"
                  role="slider"
                  :aria-label="tLocal('track.default')"
                  :aria-valuemin="0"
                  :aria-valuemax="100"
                  :aria-valuenow="progressPercent"
                  :aria-valuetext="sliderTrackText"
                  @pointerdown.prevent="startDrag"
                  @keydown="handleThumbKeydown"
                >
                  <span class="thumb-core"></span>
                </button>
              </div>
            </div>

            <div
              class="slider-note"
              :data-state="statusKey"
              role="status"
              aria-live="polite"
            >
              <span class="slider-note-dot"></span>
              <span class="slider-note-text">{{ modalTipText }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style>
.slider-captcha-plugin {
  width: 100%;
  color-scheme: light;
}

.slider-captcha-plugin,
.captcha-floating-layer {
  --captcha-accent: rgb(37 99 235);
  --captcha-accent-soft: rgb(219 234 254);
  --captcha-accent-subtle: rgb(239 246 255);
  --captcha-accent-ink: rgb(30 64 175);
  --captcha-border: rgb(226 232 240);
  --captcha-border-strong: rgb(203 213 225);
  --captcha-surface: rgb(255 255 255);
  --captcha-surface-muted: rgb(248 250 252);
  --captcha-surface-elevated: rgb(255 255 255 / 0.84);
  --captcha-track: rgb(241 245 249);
  --captcha-track-strong: rgb(225 231 239);
  --captcha-text: rgb(15 23 42);
  --captcha-text-secondary: rgb(100 116 139);
  --captcha-overlay: rgb(15 23 42 / 0.18);
  --captcha-shadow: 0 24px 60px rgb(15 23 42 / 0.18);
  --captcha-focus-ring: 0 0 0 4px rgb(59 130 246 / 0.18);
  --captcha-danger: rgb(220 38 38);
  --captcha-danger-border: rgb(252 165 165);
  --captcha-danger-soft: rgb(254 242 242);
  --captcha-success: rgb(5 150 105);
  --captcha-success-border: rgb(167 243 208);
  --captcha-success-soft: rgb(236 253 245);
  --captcha-note: rgb(148 163 184);
  --captcha-board-tint: linear-gradient(
    180deg,
    rgb(248 250 252),
    rgb(241 245 249)
  );
  --captcha-track-fill: linear-gradient(
    90deg,
    rgb(219 234 254 / 0.86),
    rgb(191 219 254 / 0.52)
  );
  --captcha-track-fill-retry: linear-gradient(
    90deg,
    rgb(254 226 226 / 0.84),
    rgb(254 202 202 / 0.56)
  );
  --captcha-track-fill-success: linear-gradient(
    90deg,
    rgb(209 250 229 / 0.88),
    rgb(167 243 208 / 0.54)
  );
  --captcha-thumb-bg: linear-gradient(
    180deg,
    rgb(111 160 255),
    rgb(73 126 246)
  );
  --captcha-thumb-bg-active: linear-gradient(
    180deg,
    rgb(124 171 255),
    rgb(66 118 237)
  );
  --captcha-thumb-border: rgb(92 145 255 / 0.96);
  --captcha-board-loading-bg: rgb(255 255 255 / 0.72);
}

html.dark .slider-captcha-plugin,
html.dark .captcha-floating-layer,
body.dark .slider-captcha-plugin,
body.dark .captcha-floating-layer,
[data-theme="dark"] .slider-captcha-plugin,
[data-theme="dark"] .captcha-floating-layer {
  color-scheme: dark;
  --captcha-accent: rgb(96 165 250);
  --captcha-accent-soft: rgb(30 41 59);
  --captcha-accent-subtle: rgb(15 23 42);
  --captcha-accent-ink: rgb(191 219 254);
  --captcha-border: rgb(51 65 85);
  --captcha-border-strong: rgb(71 85 105);
  --captcha-surface: rgb(15 23 42 / 0.96);
  --captcha-surface-muted: rgb(15 23 42 / 0.92);
  --captcha-surface-elevated: rgb(30 41 59 / 0.88);
  --captcha-track: rgb(30 41 59);
  --captcha-track-strong: rgb(51 65 85);
  --captcha-text: rgb(226 232 240);
  --captcha-text-secondary: rgb(148 163 184);
  --captcha-overlay: rgb(2 6 23 / 0.46);
  --captcha-shadow: 0 32px 80px rgb(2 6 23 / 0.58);
  --captcha-focus-ring: 0 0 0 4px rgb(96 165 250 / 0.22);
  --captcha-danger: rgb(248 113 113);
  --captcha-danger-border: rgb(127 29 29);
  --captcha-danger-soft: rgb(69 10 10 / 0.42);
  --captcha-success: rgb(52 211 153);
  --captcha-success-border: rgb(6 78 59);
  --captcha-success-soft: rgb(2 44 34 / 0.58);
  --captcha-note: rgb(100 116 139);
  --captcha-board-tint: linear-gradient(180deg, rgb(15 23 42), rgb(2 6 23));
  --captcha-track-fill: linear-gradient(
    90deg,
    rgb(30 64 175 / 0.48),
    rgb(37 99 235 / 0.26)
  );
  --captcha-track-fill-retry: linear-gradient(
    90deg,
    rgb(127 29 29 / 0.58),
    rgb(153 27 27 / 0.28)
  );
  --captcha-track-fill-success: linear-gradient(
    90deg,
    rgb(6 78 59 / 0.62),
    rgb(16 185 129 / 0.26)
  );
  --captcha-thumb-bg: linear-gradient(180deg, rgb(30 41 59), rgb(15 23 42));
  --captcha-thumb-bg-active: linear-gradient(
    180deg,
    rgb(88 134 246),
    rgb(49 92 206)
  );
  --captcha-thumb-border: rgb(86 132 236 / 0.96);
  --captcha-board-loading-bg: rgb(2 6 23 / 0.58);
}

html.dark .captcha-floating-layer .board-host,
body.dark .captcha-floating-layer .board-host,
[data-theme="dark"] .captcha-floating-layer .board-host {
  border-color: rgb(71 85 105);
  background: rgb(15 23 42 / 0.96);
}

html.dark .captcha-floating-layer .captcha-board,
body.dark .captcha-floating-layer .captcha-board,
[data-theme="dark"] .captcha-floating-layer .captcha-board {
  border-color: rgb(71 85 105);
}

.slider-captcha-plugin .captcha-trigger {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 50px;
  padding: 0 14px;
  overflow: hidden;
  border: 1px solid var(--captcha-border);
  border-radius: 14px;
  background: linear-gradient(
    180deg,
    var(--captcha-surface),
    var(--captcha-surface-muted)
  );
  box-shadow:
    0 10px 24px rgb(15 23 42 / 0.04),
    inset 0 1px 0 rgb(255 255 255 / 0.7);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease,
    background-color 0.18s ease;
}

.slider-captcha-plugin .captcha-trigger::before {
  position: absolute;
  inset: 0;
  content: "";
  background: linear-gradient(
    120deg,
    transparent 0%,
    rgb(255 255 255 / 0.08) 22%,
    transparent 48%
  );
  opacity: 0;
  transform: translateX(-32%);
  transition:
    opacity 0.2s ease,
    transform 0.3s ease;
  pointer-events: none;
}

.slider-captcha-plugin .captcha-trigger:hover:not(:disabled) {
  border-color: var(--captcha-border-strong);
  box-shadow:
    0 14px 30px rgb(37 99 235 / 0.1),
    inset 0 1px 0 rgb(255 255 255 / 0.72);
  transform: translateY(-1px);
}

.slider-captcha-plugin .captcha-trigger:hover:not(:disabled)::before {
  opacity: 1;
  transform: translateX(0);
}

.slider-captcha-plugin .captcha-trigger:focus-visible {
  outline: none;
  box-shadow: var(--captcha-focus-ring);
}

.slider-captcha-plugin .captcha-trigger.is-retry {
  border-color: var(--captcha-danger-border);
}

.slider-captcha-plugin .captcha-trigger.is-solved {
  border-color: var(--captcha-success-border);
  background: linear-gradient(
    180deg,
    var(--captcha-success-soft),
    var(--captcha-surface)
  );
  cursor: default;
}

.slider-captcha-plugin .captcha-trigger:disabled {
  opacity: 1;
}

.slider-captcha-plugin .trigger-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--captcha-accent-subtle);
  box-shadow: inset 0 0 0 1px rgb(191 219 254 / 0.46);
  flex: none;
}

.slider-captcha-plugin .trigger-icon-core {
  position: relative;
  width: 12px;
  height: 6px;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.94);
  box-shadow: inset 0 0 0 1px rgb(191 219 254 / 0.52);
}

.slider-captcha-plugin .trigger-icon-core::before {
  content: "";
  position: absolute;
  top: 1px;
  left: 2px;
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: var(--captcha-accent);
  box-shadow: 0 0 0 1px rgb(255 255 255 / 0.58);
}

.slider-captcha-plugin .trigger-copy {
  display: flex;
  min-width: 0;
  flex: 1;
}

.slider-captcha-plugin .trigger-title {
  color: var(--captcha-text);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slider-captcha-plugin .trigger-meta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex: none;
  color: var(--captcha-text-secondary);
}

.slider-captcha-plugin .trigger-action-text {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--captcha-accent-subtle);
  color: var(--captcha-accent-ink);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.slider-captcha-plugin .trigger-arrow-icon {
  width: 7px;
  height: 7px;
  margin-right: 2px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(-45deg);
  transition: transform 0.18s ease;
}

.slider-captcha-plugin
  .captcha-trigger:hover:not(:disabled)
  .trigger-arrow-icon {
  transform: translateX(2px) rotate(-45deg);
}

.slider-captcha-plugin .captcha-trigger.is-retry .trigger-meta,
.slider-captcha-plugin .captcha-trigger.is-retry .trigger-action-text {
  color: var(--captcha-danger);
}

.slider-captcha-plugin .captcha-trigger.is-solved .trigger-meta,
.slider-captcha-plugin .captcha-trigger.is-solved .trigger-action-text {
  color: var(--captcha-success);
}

.slider-captcha-plugin .captcha-trigger.is-retry .trigger-action-text {
  background: var(--captcha-danger-soft);
}

.slider-captcha-plugin .captcha-trigger.is-solved .trigger-action-text {
  background: var(--captcha-success-soft);
}

.captcha-floating-layer {
  position: fixed;
  inset: 0;
  z-index: 2400;
  background: linear-gradient(
    180deg,
    rgb(15 23 42 / 0.06),
    var(--captcha-overlay)
  );
  backdrop-filter: blur(10px);
}

.captcha-floating-layer .captcha-modal-panel {
  position: fixed;
  overflow: visible;
  border: 1px solid rgb(215 223 235);
  border-top: 3px solid rgb(95 140 255);
  border-radius: 12px;
  padding: 14px 14px 14px;
  background: linear-gradient(
    180deg,
    var(--captcha-surface),
    var(--captcha-surface-muted)
  );
  box-shadow:
    0 18px 40px rgb(15 23 42 / 0.12),
    0 2px 6px rgb(15 23 42 / 0.05);
  animation: modal-rise 0.18s ease;
}

.captcha-floating-layer .captcha-modal-panel[data-state="retry"] {
  border-color: var(--captcha-danger-border);
}

.captcha-floating-layer .captcha-modal-panel[data-state="success"] {
  border-color: var(--captcha-success-border);
}

.captcha-floating-layer .panel-caret {
  position: absolute;
  top: -7px;
  left: calc(var(--panel-caret-left, 48px) - 7px);
  width: 14px;
  height: 14px;
  border-top: 1px solid rgb(215 223 235);
  border-left: 1px solid rgb(215 223 235);
  background: var(--captcha-surface);
  transform: rotate(45deg);
}

.captcha-floating-layer
  .captcha-modal-panel[data-placement="top"]
  .panel-caret {
  top: auto;
  bottom: -7px;
  border-top: none;
  border-left: none;
  border-right: 1px solid rgb(215 223 235);
  border-bottom: 1px solid rgb(215 223 235);
}

.captcha-floating-layer
  .captcha-modal-panel[data-placement="center"]
  .panel-caret {
  display: none;
}

.captcha-floating-layer .modal-header {
  display: flex;
  position: relative;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 8px;
}

.captcha-floating-layer .modal-title-group {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  min-width: 0;
  text-align: center;
}

.captcha-floating-layer .modal-title {
  margin: 0;
  color: var(--captcha-text);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0;
}

.captcha-floating-layer .modal-subtitle {
  margin: 5px 0 0;
  color: var(--captcha-text-secondary);
  font-size: 11px;
  line-height: 1.35;
}

.captcha-floating-layer .modal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  position: absolute;
  right: 0;
  top: 0;
}

.captcha-floating-layer .modal-refresh {
  min-height: 24px;
  padding: 0 10px;
  border: 1px solid var(--captcha-border);
  border-radius: 999px;
  background: linear-gradient(180deg, rgb(255 255 255), rgb(247 249 252));
  color: var(--captcha-text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease;
}

.captcha-floating-layer .modal-refresh:hover:not(:disabled) {
  color: var(--captcha-text);
  border-color: var(--captcha-border-strong);
  box-shadow: 0 4px 12px rgb(15 23 42 / 0.08);
}

.captcha-floating-layer .modal-refresh:focus-visible,
.captcha-floating-layer .modal-close-button:focus-visible,
.captcha-floating-layer .slider-thumb:focus-visible {
  outline: none;
  box-shadow: var(--captcha-focus-ring);
}

.captcha-floating-layer .modal-refresh:disabled,
.captcha-floating-layer .modal-close-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.captcha-floating-layer .modal-close-button {
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

.captcha-floating-layer .modal-close-button:hover {
  background: rgb(15 23 42 / 0.04);
}

.captcha-floating-layer .close-icon {
  position: relative;
  display: block;
  width: 14px;
  height: 14px;
  margin: 0 auto;
}

.captcha-floating-layer .close-icon::before,
.captcha-floating-layer .close-icon::after {
  content: "";
  position: absolute;
  top: 6px;
  left: 1px;
  width: 12px;
  height: 1.5px;
  border-radius: 999px;
  background: rgb(148 163 184);
}

.captcha-floating-layer .close-icon::before {
  transform: rotate(45deg);
}

.captcha-floating-layer .close-icon::after {
  transform: rotate(-45deg);
}

.captcha-floating-layer .modal-stage {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.captcha-floating-layer .board-host {
  display: flex;
  justify-content: center;
  width: 100%;
  padding: 4px;
  border: 1px solid rgb(223 229 239);
  border-radius: 16px;
  background: linear-gradient(180deg, rgb(255 255 255), rgb(249 250 252));
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.9),
    0 1px 2px rgb(15 23 42 / 0.03);
}

.captcha-floating-layer .captcha-board {
  position: relative;
  overflow: hidden;
  border: 1px solid rgb(225 231 239);
  border-radius: 13px;
  background: var(--captcha-board-tint);
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.22),
    inset 0 0 0 1px rgb(255 255 255 / 0.08);
}

.captcha-floating-layer .captcha-board.is-solved::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgb(16 185 129 / 0.04),
    rgb(16 185 129 / 0.1)
  );
}

.captcha-floating-layer .board-empty {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
}

.captcha-floating-layer .board-empty-title {
  color: var(--captcha-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.captcha-floating-layer .board-canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
}

.captcha-floating-layer .piece-canvas {
  position: absolute;
  display: block;
  pointer-events: none;
  filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.35))
    drop-shadow(0 3px 8px rgb(0 0 0 / 0.18));
  transition:
    left 0.14s ease,
    top 0.14s ease,
    filter 0.14s ease;
  will-change: left;
}

.captcha-floating-layer .piece-canvas.is-dragging {
  filter: drop-shadow(0 2px 5px rgb(0 0 0 / 0.4))
    drop-shadow(0 5px 14px rgb(0 0 0 / 0.22));
  transition: none;
}

.captcha-floating-layer .piece-canvas.is-solved {
  filter: drop-shadow(0 2px 4px rgb(0 0 0 / 0.25))
    drop-shadow(0 0 8px rgb(22 163 74 / 0.3));
}

.captcha-floating-layer .board-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: var(--captcha-board-loading-bg);
  color: var(--captcha-text);
  font-size: 13px;
  font-weight: 600;
  backdrop-filter: blur(8px);
}

.captcha-floating-layer .loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--captcha-accent);
  box-shadow: 0 0 0 6px rgb(219 234 254 / 0.48);
  animation: pulse-dot 1s ease-in-out infinite;
}

.captcha-floating-layer .slider-track {
  position: relative;
  height: 42px;
  overflow: hidden;
  border: 1px solid var(--captcha-track-strong);
  border-radius: 12px;
  background: linear-gradient(180deg, rgb(246 248 252), rgb(232 238 246));
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.7),
    inset 0 -1px 0 rgb(203 213 225 / 0.38),
    0 1px 2px rgb(15 23 42 / 0.03);
}

.captcha-floating-layer .slider-track[data-state="retry"] {
  border-color: var(--captcha-danger-border);
}

.captcha-floating-layer .slider-track[data-state="success"] {
  border-color: var(--captcha-success-border);
}

.captcha-floating-layer .slider-track::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.24);
  pointer-events: none;
}

.captcha-floating-layer .track-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    rgb(171 205 255 / 0.48),
    rgb(109 160 255 / 0.22)
  );
  box-shadow: inset 0 0 0 1px rgb(191 219 254 / 0.16);
  transition: width 0.14s ease;
}

.captcha-floating-layer .slider-track.is-dragging .track-fill {
  transition: none;
}

.captcha-floating-layer .slider-track[data-state="retry"] .track-fill {
  background: var(--captcha-track-fill-retry);
}

.captcha-floating-layer .slider-track[data-state="success"] .track-fill {
  background: var(--captcha-track-fill-success);
}

.captcha-floating-layer .track-copy {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 60px;
  color: var(--captcha-text-secondary);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.01em;
  pointer-events: none;
  user-select: none;
  white-space: nowrap;
}

.captcha-floating-layer .slider-thumb {
  position: absolute;
  top: 1px;
  bottom: 1px;
  border: 1px solid var(--captcha-thumb-border);
  border-radius: 11px;
  background: var(--captcha-thumb-bg);
  box-shadow:
    0 10px 18px rgb(76 118 214 / 0.32),
    0 2px 4px rgb(15 23 42 / 0.16),
    inset 0 1px 0 rgb(255 255 255 / 0.4),
    inset 0 -1px 0 rgb(37 99 235 / 0.28);
  cursor: grab;
  transition:
    transform 0.14s ease,
    box-shadow 0.14s ease,
    border-color 0.14s ease,
    background 0.14s ease;
}

.captcha-floating-layer .slider-thumb:hover:not(:disabled) {
  border-color: rgb(74 126 246 / 0.98);
}

.captcha-floating-layer .slider-thumb.is-dragging {
  cursor: grabbing;
  transform: translateY(-1px) scale(1.01);
  background: var(--captcha-thumb-bg-active);
  box-shadow:
    0 14px 26px rgb(76 118 214 / 0.38),
    0 6px 12px rgb(15 23 42 / 0.2),
    inset 0 1px 0 rgb(255 255 255 / 0.46),
    inset 0 -1px 0 rgb(29 78 216 / 0.32);
}

.captcha-floating-layer .slider-thumb.is-solved {
  border-color: var(--captcha-success-border);
  background: linear-gradient(
    180deg,
    var(--captcha-success-soft),
    var(--captcha-surface)
  );
}

.captcha-floating-layer .slider-thumb:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.captcha-floating-layer .thumb-core {
  position: absolute;
  inset: 0;
}

.captcha-floating-layer .thumb-core::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 2px;
  height: 14px;
  margin-top: -7px;
  margin-left: -1px;
  background: rgb(255 255 255 / 0.92);
  border-radius: 1px;
  box-shadow:
    -5px 0 0 rgb(255 255 255 / 0.92),
    5px 0 0 rgb(255 255 255 / 0.92);
}

.captcha-floating-layer .thumb-core::after {
  display: none;
}

.captcha-floating-layer .slider-note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 4px 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--captcha-text-secondary);
  font-size: 11px;
  line-height: 1.35;
}

.captcha-floating-layer .slider-note-dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--captcha-note);
  flex: none;
}

.captcha-floating-layer .slider-note[data-state="retry"] {
  color: var(--captcha-danger);
  border-color: var(--captcha-danger-border);
  background: var(--captcha-danger-soft);
}

.captcha-floating-layer .slider-note[data-state="retry"] .slider-note-dot {
  background: var(--captcha-danger);
}

.captcha-floating-layer .slider-note[data-state="success"] {
  color: var(--captcha-success);
  border-color: var(--captcha-success-border);
  background: var(--captcha-success-soft);
}

.captcha-floating-layer .slider-note[data-state="success"] .slider-note-dot {
  background: var(--captcha-success);
}

.captcha-floating-layer .slider-note[data-state="loading"] .slider-note-dot {
  background: var(--captcha-accent);
}

.captcha-floating-layer .slider-note-text {
  min-width: 0;
}

.slider-captcha-fade-enter-active,
.slider-captcha-fade-leave-active {
  transition: opacity 0.22s ease;
}

.slider-captcha-fade-enter-from,
.slider-captcha-fade-leave-to {
  opacity: 0;
}

@keyframes pulse-dot {
  0%,
  100% {
    transform: scale(0.92);
    opacity: 0.82;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes modal-rise {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 640px) {
  .slider-captcha-plugin .captcha-trigger {
    min-height: 48px;
    padding-right: 12px;
  }

  .slider-captcha-plugin .trigger-action-text {
    padding-inline: 8px;
  }

  .captcha-floating-layer .modal-header {
    gap: 12px;
  }

  .captcha-floating-layer .modal-actions {
    align-items: flex-start;
  }

  .captcha-floating-layer .captcha-modal-panel {
    padding: 18px;
  }

  .captcha-floating-layer .track-copy {
    padding: 0 68px;
  }

  .captcha-floating-layer .slider-note {
    padding-inline: 10px;
  }
}
</style>
