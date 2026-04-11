<script setup lang="ts">
import { getSliderCaptchaShared } from "./slider-captcha-shared";
import { useSliderCaptchaController } from "./use-slider-captcha-controller";
import { useSliderCaptchaCopy } from "./use-slider-captcha-copy";

import type { SliderCaptchaResult } from "./types";

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

const {
  boardCanvasRef,
  boardHostRef,
  boardStyle,
  challenge,
  closeModal,
  dragging,
  getResult,
  handleThumbKeydown,
  handleTriggerClick,
  handleWidth,
  handleX,
  loading,
  modalPanelRef,
  modalPanelStyle,
  modalPlacement,
  modalVisible,
  pieceCanvasRef,
  pieceStyle,
  progressPercent,
  refresh,
  solved,
  startDrag,
  statusKey,
  triggerButtonRef,
} = useSliderCaptchaController({
  action: () => props.action,
  difficulty: () => props.difficulty,
  disabled: () => props.disabled,
  endpoint: () => props.endpoint,
  onError: (error) => emit("error", error),
  onVerified: (result) => emit("verified", result),
});

const {
  modalStatusText,
  modalTipText,
  showTrackCopy,
  sliderTrackText,
  tLocal,
  triggerActionLabel,
  triggerTitle,
} = useSliderCaptchaCopy({
  challenge,
  dragging,
  handleX,
  loading,
  solved,
  statusKey,
  translate: (key) => getSliderCaptchaShared()?.$t?.(key),
});

defineExpose({
  getResult,
  refresh,
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
