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
import {
  bindSliderCaptchaWindowEvents,
  resolveSliderThumbKeyboardAction,
} from "./slider-captcha-a11y";
import {
  getSliderCaptchaDisplayWidth,
  resolveSliderCaptchaModalLayout,
} from "./slider-captcha-modal-helpers";
import type {
  SliderCaptchaModalPlacement,
  SliderCaptchaModalPosition,
} from "./slider-captcha-modal-helpers";
import { createSliderCaptchaStateMachine } from "./slider-captcha-state-machine";
import { useSliderCaptchaChallenge } from "./use-slider-captcha-challenge";

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
const modalPlacement = ref<SliderCaptchaModalPlacement>("top");
const modalPosition = ref<SliderCaptchaModalPosition>({
  caretLeft: 48,
  left: 12,
  top: 12,
  width: 360,
});

let pointerId: null | number = null;
let pointerStartX = 0;
let pointerStartHandleX = 0;
let unbindWindowEvents: null | (() => void) = null;

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

const stateMachine = createSliderCaptchaStateMachine({
  challenge,
  challengeId,
  detectedTargetLeft,
  dragX,
  modalVisible,
  onRefresh: refresh,
  onVerified: (result) => emit("verified", result),
  scaleRatio: () => scaleRatio.value,
  solved,
  solvedOffset,
  statusKey,
});

function clearRetryTimer(): void {
  stateMachine.clearRetryTimer();
}

function clearSuccessCloseTimer(): void {
  stateMachine.clearSuccessCloseTimer();
}

function updateDisplayWidth(): void {
  displayWidth.value = getSliderCaptchaDisplayWidth(
    boardHostRef.value?.clientWidth,
  );
}

function updateModalPosition(): void {
  const triggerEl = triggerButtonRef.value;
  if (!triggerEl) {
    return;
  }
  const { placement, position } = resolveSliderCaptchaModalLayout(
    triggerEl.getBoundingClientRect(),
    {
      modalHeight: modalPanelRef.value?.offsetHeight ?? 336,
    },
  );
  modalPlacement.value = placement;
  modalPosition.value = position;
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

function prepareInteraction(): void {
  stateMachine.prepareInteraction();
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
  stateMachine.completeAttempt();
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

  switch (resolveSliderThumbKeyboardAction(event)) {
    case "decrease": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleX.value - step);
      return;
    }
    case "increase": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleX.value + step);
      return;
    }
    case "to-end": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(handleTravelMax.value);
      return;
    }
    case "home": {
      event.preventDefault();
      prepareInteraction();
      setHandlePosition(0);
      return;
    }
    case "attempt": {
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
  stateMachine.resetFailCounter();
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
  stateMachine.resetFailCounter();
  resetChallengeState();
  if (modalVisible.value) {
    void safeLoadChallenge();
  }
}

function getResult(): SliderCaptchaResult | null {
  const result = stateMachine.getSolvedResult();
  if (!result) {
    openModal(statusKey.value === "retry" || !challenge.value);
    return null;
  }
  return result;
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
  unbindWindowEvents = bindSliderCaptchaWindowEvents({
    onEscape: () => {
      if (modalVisible.value) {
        closeModal();
      }
    },
    onResize: handleWindowResize,
    onScroll: handleWindowScroll,
  });
});

onBeforeUnmount(() => {
  stateMachine.dispose();
  resetChallengeState();
  modalVisible.value = false;
  unbindWindowEvents?.();
  unbindWindowEvents = null;
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


<style src="./slider-captcha.css"></style>
