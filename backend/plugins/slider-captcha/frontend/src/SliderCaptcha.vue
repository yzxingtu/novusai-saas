<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';

import background1 from './assets/backgrounds/slider-bg-01.jpg';
import background2 from './assets/backgrounds/slider-bg-02.jpg';
import background3 from './assets/backgrounds/slider-bg-03.jpg';
import background4 from './assets/backgrounds/slider-bg-04.jpg';
import type { SliderCaptchaSharedAPI } from './types';

const PROVIDER_CODE = 'slider';
const LOCALE_PREFIX = 'plugin.slider-captcha';
const CAPTURE_LEFT_PADDING = 3;
const FALLBACK_TEXT = {
  modalEyebrow: 'SECURITY CHECK',
  modalSubtitle:
    'Drag the slider so the puzzle piece returns to the missing slot.',
  modalTipDefault:
    'Align the puzzle piece and sign-in will continue automatically.',
  modalTipRetry: 'The piece is not aligned. Please drag again.',
  modalTipSuccess: 'Verification succeeded. Continuing sign-in...',
  modal: {
    close: 'Close dialog',
  },
  modalTitle: 'Complete security verification',
  status: {
    default: 'Drag the slider to verify',
    loading: 'Loading challenge...',
    refresh: 'Refresh',
    retry: 'Try again',
    success: 'Verified',
  },
  track: {
    default: 'Drag right to complete verification',
    loading: 'Loading challenge...',
    retry: 'Drag right to try again',
    success: 'Verification completed',
  },
  trigger: {
    action: {
      default: 'Verify',
      retry: 'Retry',
      success: 'Verified',
    },
    title: {
      default: 'Complete security verification',
      retry: 'Verification failed, please retry',
      success: 'Security verification completed',
    },
  },
} as const;

interface CaptchaResult {
  captchaCode: string;
  challengeId: string;
  provider: string;
}

interface ChallengePayload {
  background_index?: number;
  background_url?: string;
  canvas_height: number;
  canvas_width: number;
  circle_radius: number;
  piece_x: number;
  piece_y: number;
  square_length: number;
  tolerance_px: number;
}

interface ChallengeResponsePayload {
  challenge_id: string;
  payload: ChallengePayload;
}

const props = withDefaults(
  defineProps<{
    action?: string;
    disabled?: boolean;
    difficulty?: 'easy' | 'hard' | 'medium';
    endpoint: string;
  }>(),
  {
    action: 'login',
    disabled: false,
    difficulty: 'medium',
  },
);

const emit = defineEmits<{
  (e: 'error', error: Error): void;
  (e: 'verified', result: CaptchaResult): void;
}>();

const bundledBackgrounds = [background1, background2, background3, background4];

const triggerButtonRef = ref<HTMLElement | null>(null);
const modalPanelRef = ref<HTMLElement | null>(null);
const boardHostRef = ref<HTMLElement | null>(null);
const boardCanvasRef = ref<HTMLCanvasElement | null>(null);
const pieceCanvasRef = ref<HTMLCanvasElement | null>(null);

const challengeId = ref('');
const challenge = ref<ChallengePayload | null>(null);
const loading = ref(false);
const dragX = ref(0);
const solved = ref(false);
const solvedOffset = ref<number | null>(null);
const statusKey = ref<'default' | 'loading' | 'retry' | 'success'>('default');
const displayWidth = ref(320);
const dragging = ref(false);
const renderToken = ref(0);
const modalVisible = ref(false);
const modalPlacement = ref<'bottom' | 'top'>('bottom');
const modalPosition = ref({
  caretLeft: 48,
  left: 12,
  top: 12,
  width: 360,
});

let pointerId: null | number = null;
let pointerStartX = 0;
let pointerStartHandleX = 0;
let retryTimer: null | number = null;
let successCloseTimer: null | number = null;
let challengeRequestToken = 0;

function getShared(): SliderCaptchaSharedAPI | undefined {
  return (window as unknown as { NovusPluginShared?: SliderCaptchaSharedAPI })
    .NovusPluginShared;
}

function tLocal(path: string): string {
  const fullKey = `${LOCALE_PREFIX}.${path}`;
  const translated = getShared()?.$t?.(fullKey);
  if (!translated || translated === fullKey) {
    const segments = path.split('.');
    let current: unknown = FALLBACK_TEXT;
    for (const segment of segments) {
      if (!current || typeof current !== 'object') {
        return fullKey;
      }
      current = (current as Record<string, unknown>)[segment];
    }
    return typeof current === 'string' ? current : fullKey;
  }
  return translated;
}

function getPieceCaptureLength(payload: ChallengePayload): number {
  return payload.square_length + 2 * payload.circle_radius + CAPTURE_LEFT_PADDING;
}

function getPieceCaptureLeft(payload: ChallengePayload): number {
  return Math.max(0, payload.piece_x - CAPTURE_LEFT_PADDING);
}

function getPieceCaptureTop(payload: ChallengePayload): number {
  return Math.max(0, payload.piece_y - 2 * payload.circle_radius - 1);
}

function getPieceLocalOrigin(payload: ChallengePayload): { x: number; y: number } {
  return {
    x: payload.piece_x - getPieceCaptureLeft(payload),
    y: payload.piece_y - getPieceCaptureTop(payload),
  };
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
  return getPieceCaptureLength(challenge.value);
});

const pieceTravelMax = computed(() => {
  if (!challenge.value) {
    return 0;
  }
  return Math.max(0, boardWidth.value - pieceLength.value * scaleRatio.value);
});

const handleWidth = computed(() => {
  return Math.max(54, Math.min(58, boardWidth.value * 0.17));
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
      height: '0px',
      left: '0px',
      top: '0px',
      width: '0px',
    };
  }

  const pieceTop = getPieceCaptureTop(challenge.value) * scaleRatio.value;
  const pieceSize = pieceLength.value * scaleRatio.value;

  return {
    height: `${pieceSize}px`,
    left: `${dragX.value}px`,
    top: `${pieceTop}px`,
    width: `${pieceSize}px`,
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
    '--panel-caret-left': `${modalPosition.value.caretLeft}px`,
    left: `${modalPosition.value.left}px`,
    top: `${modalPosition.value.top}px`,
    width: `${modalPosition.value.width}px`,
  } as Record<string, string>;
});

const triggerTitle = computed(() => {
  if (solved.value) {
    return tLocal('trigger.title.success');
  }
  if (statusKey.value === 'retry') {
    return tLocal('trigger.title.retry');
  }
  if (loading.value) {
    return tLocal('status.loading');
  }
  return tLocal('trigger.title.default');
});

const triggerActionLabel = computed(() => {
  if (solved.value) {
    return tLocal('trigger.action.success');
  }
  if (statusKey.value === 'retry') {
    return tLocal('trigger.action.retry');
  }
  return tLocal('trigger.action.default');
});

const modalStatusText = computed(() => tLocal(`status.${statusKey.value}`));

const modalTipText = computed(() => {
  if (solved.value) {
    return tLocal('modalTipSuccess');
  }
  if (statusKey.value === 'retry') {
    return tLocal('modalTipRetry');
  }
  return tLocal('modalTipDefault');
});

const sliderTrackText = computed(() => {
  if (loading.value) {
    return tLocal('track.loading');
  }
  if (solved.value) {
    return tLocal('track.success');
  }
  if (statusKey.value === 'retry') {
    return tLocal('track.retry');
  }
  return tLocal('track.default');
});

const showTrackCopy = computed(() => {
  return (
    Boolean(challenge.value) &&
    !loading.value &&
    !solved.value &&
    statusKey.value === 'default' &&
    !dragging.value &&
    handleX.value <= 1
  );
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
  displayWidth.value = Math.max(300, Math.min(360, width));
}

function updateModalPosition(): void {
  const triggerEl = triggerButtonRef.value;
  if (!triggerEl) {
    return;
  }

  const rect = triggerEl.getBoundingClientRect();
  const viewportPadding = 12;
  const panelGap = 10;
  const preferredWidth = Math.max(320, Math.min(392, rect.width + 18));
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
  let placement: 'bottom' | 'top' = 'bottom';
  let top = rect.bottom + panelGap;

  if (
    top + panelHeight > window.innerHeight - viewportPadding &&
    rect.top - panelGap - panelHeight >= viewportPadding
  ) {
    placement = 'top';
    top = rect.top - panelHeight - panelGap;
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
    caretLeft,
    left,
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

function syncDragAfterResize(previousScale: number): void {
  if (!challenge.value || previousScale <= 0) {
    return;
  }

  const pieceLeft = solved.value
    ? getPieceCaptureLeft(challenge.value)
    : dragX.value / previousScale;

  setPieceLeft(pieceLeft);
}

function resetChallengeState(): void {
  clearRetryTimer();
  clearSuccessCloseTimer();
  releaseDrag();
  challengeRequestToken += 1;
  renderToken.value += 1;
  loading.value = false;
  challengeId.value = '';
  challenge.value = null;
  dragX.value = 0;
  solved.value = false;
  solvedOffset.value = null;
  statusKey.value = 'default';
}

function tracePieceShape(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  squareLength: number,
  circleRadius: number,
) {
  const pi = Math.PI;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.arc(
    x + squareLength / 2,
    y - circleRadius + 2,
    circleRadius,
    0.72 * pi,
    2.26 * pi,
  );
  ctx.lineTo(x + squareLength, y);
  ctx.arc(
    x + squareLength + circleRadius - 2,
    y + squareLength / 2,
    circleRadius,
    1.21 * pi,
    2.78 * pi,
  );
  ctx.lineTo(x + squareLength, y + squareLength);
  ctx.lineTo(x, y + squareLength);
  ctx.arc(
    x + circleRadius - 2,
    y + squareLength / 2,
    circleRadius + 0.4,
    2.76 * pi,
    1.24 * pi,
    true,
  );
  ctx.lineTo(x, y);
}

function renderBoardSlot(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  squareLength: number,
  circleRadius: number,
) {
  tracePieceShape(ctx, x, y, squareLength, circleRadius);
  ctx.save();
  ctx.fillStyle = 'rgba(15, 23, 42, 0.3)';
  ctx.shadowColor = 'rgba(15, 23, 42, 0.18)';
  ctx.shadowBlur = 14;
  ctx.shadowOffsetY = 3;
  ctx.fill();
  ctx.restore();

  ctx.save();
  tracePieceShape(ctx, x, y, squareLength, circleRadius);
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
  ctx.stroke();
  ctx.restore();

  ctx.save();
  tracePieceShape(ctx, x, y, squareLength, circleRadius);
  ctx.clip();
  const overlay = ctx.createLinearGradient(
    x,
    y - circleRadius * 2,
    x,
    y + squareLength + circleRadius * 2,
  );
  overlay.addColorStop(0, 'rgba(255, 255, 255, 0.08)');
  overlay.addColorStop(1, 'rgba(15, 23, 42, 0.12)');
  ctx.fillStyle = overlay;
  ctx.fillRect(
    x - 8,
    y - circleRadius * 2 - 8,
    squareLength + circleRadius * 2 + 16,
    squareLength + circleRadius * 4 + 16,
  );
  ctx.restore();
}

function renderPuzzlePiece(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement,
  payload: ChallengePayload,
) {
  const captureLength = getPieceCaptureLength(payload);
  const captureLeft = getPieceCaptureLeft(payload);
  const captureTop = getPieceCaptureTop(payload);
  const localOrigin = getPieceLocalOrigin(payload);
  ctx.clearRect(0, 0, captureLength, captureLength);

  ctx.save();
  tracePieceShape(
    ctx,
    localOrigin.x,
    localOrigin.y,
    payload.square_length,
    payload.circle_radius,
  );
  ctx.clip();
  ctx.drawImage(
    image,
    captureLeft,
    captureTop,
    captureLength,
    captureLength,
    0,
    0,
    captureLength,
    captureLength,
  );
  ctx.restore();

  ctx.save();
  tracePieceShape(
    ctx,
    localOrigin.x,
    localOrigin.y,
    payload.square_length,
    payload.circle_radius,
  );
  const sheen = ctx.createLinearGradient(0, 0, 0, captureLength);
  sheen.addColorStop(0, 'rgba(255, 255, 255, 0.18)');
  sheen.addColorStop(0.46, 'rgba(255, 255, 255, 0.02)');
  sheen.addColorStop(1, 'rgba(15, 23, 42, 0.08)');
  ctx.fillStyle = sheen;
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.96)';
  ctx.stroke();
  ctx.restore();
}

function getBackgroundSource(payload: ChallengePayload): string {
  if (payload.background_url) {
    return payload.background_url;
  }
  const index = Math.max(
    0,
    Math.min(bundledBackgrounds.length - 1, payload.background_index ?? 0),
  );
  return bundledBackgrounds[index]!;
}

function renderWithImage(image: HTMLImageElement): void {
  const payload = challenge.value;
  const boardCanvas = boardCanvasRef.value;
  const pieceCanvas = pieceCanvasRef.value;
  if (!payload || !boardCanvas || !pieceCanvas) {
    return;
  }

  const captureLength = getPieceCaptureLength(payload);
  boardCanvas.width = payload.canvas_width;
  boardCanvas.height = payload.canvas_height;
  pieceCanvas.width = captureLength;
  pieceCanvas.height = captureLength;

  const boardCtx = boardCanvas.getContext('2d');
  const pieceCtx = pieceCanvas.getContext('2d');
  if (!boardCtx || !pieceCtx) {
    return;
  }

  boardCtx.clearRect(0, 0, payload.canvas_width, payload.canvas_height);
  boardCtx.drawImage(image, 0, 0, payload.canvas_width, payload.canvas_height);
  renderBoardSlot(
    boardCtx,
    payload.piece_x,
    payload.piece_y,
    payload.square_length,
    payload.circle_radius,
  );

  renderPuzzlePiece(pieceCtx, image, payload);
}

async function renderChallenge(): Promise<void> {
  const payload = challenge.value;
  if (!payload) {
    return;
  }

  const currentToken = ++renderToken.value;
  const image = new Image();
  const primarySrc = getBackgroundSource(payload);
  const fallbackIndex = Math.max(
    0,
    Math.min(bundledBackgrounds.length - 1, payload.background_index ?? 0),
  );
  const fallbackSrc =
    primarySrc === payload.background_url
      ? bundledBackgrounds[fallbackIndex]!
      : primarySrc;

  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error('background_load_failed'));
    image.src = primarySrc;
  }).catch(async () => {
    if (!fallbackSrc || fallbackSrc === primarySrc) {
      throw new Error('background_load_failed');
    }
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('background_load_failed'));
      image.src = fallbackSrc;
    });
  });

  if (currentToken !== renderToken.value) {
    return;
  }
  renderWithImage(image);
}

async function loadChallenge(): Promise<void> {
  const currentRequestToken = ++challengeRequestToken;
  clearRetryTimer();
  clearSuccessCloseTimer();
  releaseDrag();
  loading.value = true;
  solved.value = false;
  solvedOffset.value = null;
  dragX.value = 0;
  statusKey.value = 'loading';

  try {
    const shared = getShared();
    if (!shared?.requestClient) {
      throw new Error('request_client_unavailable');
    }

    const result = await shared.requestClient.post<ChallengeResponsePayload>(
      '/api/public/captcha/challenge',
      {
        action: props.action,
        endpoint: props.endpoint,
        provider_code: PROVIDER_CODE,
      },
    );
    if (!result?.payload) {
      throw new Error('challenge_request_failed');
    }
    if (currentRequestToken !== challengeRequestToken) {
      return;
    }

    challengeId.value = result.challenge_id;
    challenge.value = result.payload;
    statusKey.value = 'default';
    await nextTick();
    updateDisplayWidth();
    await renderChallenge();
    if (modalVisible.value) {
      await nextTick();
      updateModalPosition();
    }
  } catch (error) {
    if (currentRequestToken !== challengeRequestToken) {
      return;
    }
    statusKey.value = 'retry';
    emit('error', error instanceof Error ? error : new Error(String(error)));
  } finally {
    if (currentRequestToken === challengeRequestToken) {
      loading.value = false;
    }
  }
}

function releaseDrag(): void {
  pointerId = null;
  dragging.value = false;
  window.removeEventListener('pointermove', handlePointerMove);
  window.removeEventListener('pointerup', handlePointerUp);
  window.removeEventListener('pointercancel', handlePointerUp);
}

function resetDragAfterRetry(): void {
  clearRetryTimer();
  retryTimer = window.setTimeout(() => {
    dragX.value = 0;
    statusKey.value = 'default';
    retryTimer = null;
  }, 420);
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

  dragX.value = (nextHandle / handleTravelMax.value) * pieceTravelMax.value;
}

function handlePointerUp(): void {
  if (!challenge.value || pointerId === null) {
    releaseDrag();
    return;
  }

  const expectedLeft = getPieceCaptureLeft(challenge.value);
  const actualOffset = Math.round(dragX.value / scaleRatio.value);
  const tolerancePx = challenge.value.tolerance_px;

  releaseDrag();

  if (Math.abs(actualOffset - expectedLeft) <= tolerancePx) {
    dragX.value = expectedLeft * scaleRatio.value;
    solved.value = true;
    solvedOffset.value = challenge.value.piece_x;
    statusKey.value = 'success';
    emit('verified', {
      captchaCode: String(challenge.value.piece_x),
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

  solved.value = false;
  solvedOffset.value = null;
  statusKey.value = 'retry';
  resetDragAfterRetry();
}

function startDrag(event: PointerEvent): void {
  if (props.disabled || loading.value || !challenge.value || solved.value) {
    return;
  }

  clearRetryTimer();
  clearSuccessCloseTimer();
  pointerId = event.pointerId;
  dragging.value = true;
  statusKey.value = 'default';
  pointerStartX = event.clientX;
  pointerStartHandleX = handleX.value;
  window.addEventListener('pointermove', handlePointerMove);
  window.addEventListener('pointerup', handlePointerUp);
  window.addEventListener('pointercancel', handlePointerUp);
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
  openModal(statusKey.value === 'retry' || !challenge.value);
}

function refresh(): void {
  resetChallengeState();
  if (modalVisible.value) {
    void loadChallenge();
  }
}

function getResult(): CaptchaResult | null {
  if (!solved.value || !challengeId.value || solvedOffset.value == null) {
    openModal(statusKey.value === 'retry' || !challenge.value);
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

async function rerenderExistingChallenge(): Promise<void> {
  const previousScale = scaleRatio.value;
  await nextTick();
  updateDisplayWidth();
  syncDragAfterResize(previousScale);
  updateModalPosition();
  if (!challenge.value) {
    return;
  }
  try {
    await renderChallenge();
    if (modalVisible.value) {
      await nextTick();
      updateModalPosition();
    }
  } catch (error) {
    statusKey.value = 'retry';
    emit('error', error instanceof Error ? error : new Error(String(error)));
  }
}

function handleWindowKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && modalVisible.value) {
    closeModal();
  }
}

function handleWindowResize(): void {
  if (!modalVisible.value) {
    return;
  }
  void rerenderExistingChallenge();
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
      void loadChallenge();
    }
  },
);

watch(
  modalVisible,
  async (visible) => {
    if (!visible) {
      return;
    }
    await nextTick();
    updateDisplayWidth();
    updateModalPosition();
    if (!challenge.value) {
      void loadChallenge();
      return;
    }
    await rerenderExistingChallenge();
  },
);

onMounted(() => {
  window.addEventListener('resize', handleWindowResize);
  window.addEventListener('scroll', handleWindowScroll, true);
  window.addEventListener('keydown', handleWindowKeydown);
});

onBeforeUnmount(() => {
  resetChallengeState();
  modalVisible.value = false;
  window.removeEventListener('resize', handleWindowResize);
  window.removeEventListener('scroll', handleWindowScroll, true);
  window.removeEventListener('keydown', handleWindowKeydown);
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
          :style="modalPanelStyle"
          role="dialog"
          aria-modal="true"
          :aria-label="tLocal('modalTitle')"
        >
          <span class="panel-caret" aria-hidden="true"></span>
          <div class="modal-header">
            <div class="modal-title-group">
              <h3 class="modal-title">{{ tLocal('modalTitle') }}</h3>
              <p class="modal-subtitle">{{ tLocal('modalSubtitle') }}</p>
            </div>
            <div class="modal-actions">
              <button
                class="modal-refresh"
                type="button"
                :disabled="props.disabled || loading"
                @click="refresh"
              >
                {{ tLocal('status.refresh') }}
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
                  <span>{{ tLocal('status.loading') }}</span>
                </div>
              </div>
            </div>

            <div class="captcha-slider">
              <div
                class="slider-track"
                :style="{ '--track-handle-width': `${handleWidth}px` }"
              >
                <div
                  class="track-fill"
                  :style="{ width: `${handleX + handleWidth}px` }"
                ></div>
                <div v-if="showTrackCopy" class="track-copy">
                  {{ tLocal('track.default') }}
                </div>
                <button
                  name="captcha-action"
                  type="button"
                  class="slider-thumb"
                  :class="{ 'is-dragging': dragging, 'is-solved': solved }"
                  :disabled="props.disabled || loading"
                  :style="{ left: `${handleX}px`, width: `${handleWidth}px` }"
                  @pointerdown.prevent="startDrag"
                >
                  <span class="thumb-core"></span>
                </button>
              </div>
            </div>

            <div class="slider-note" :data-state="statusKey">
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
}

.slider-captcha-plugin,
.captcha-floating-layer {
  --captcha-accent: rgb(37 99 235);
  --captcha-accent-soft: rgb(219 234 254);
  --captcha-accent-subtle: rgb(239 246 255);
  --captcha-border: rgb(226 232 240);
  --captcha-border-strong: rgb(203 213 225);
  --captcha-surface: rgb(255 255 255);
  --captcha-surface-muted: rgb(248 250 252);
  --captcha-track: rgb(241 245 249);
  --captcha-text: rgb(17 24 39);
  --captcha-text-secondary: rgb(100 116 139);
  --captcha-shadow: 0 24px 60px rgb(15 23 42 / 0.16);
}

.slider-captcha-plugin .captcha-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid var(--captcha-border);
  border-radius: 12px;
  background: var(--captcha-surface);
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.02);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.slider-captcha-plugin .captcha-trigger:hover:not(:disabled) {
  border-color: rgb(147 197 253);
  box-shadow: 0 8px 18px rgb(37 99 235 / 0.08);
}

.slider-captcha-plugin .captcha-trigger.is-retry {
  border-color: rgb(252 165 165);
}

.slider-captcha-plugin .captcha-trigger.is-solved {
  border-color: rgb(167 243 208);
  background: rgb(240 253 250);
  cursor: default;
}

.slider-captcha-plugin .captcha-trigger:disabled {
  opacity: 1;
}

.slider-captcha-plugin .trigger-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: var(--captcha-accent-subtle);
  box-shadow: inset 0 0 0 1px rgb(191 219 254 / 0.65);
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
  content: '';
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
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slider-captcha-plugin .trigger-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: none;
  color: var(--captcha-text-secondary);
}

.slider-captcha-plugin .trigger-action-text {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.slider-captcha-plugin .trigger-arrow-icon {
  width: 7px;
  height: 7px;
  margin-right: 2px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(-45deg);
}

.slider-captcha-plugin .captcha-trigger.is-retry .trigger-meta,
.slider-captcha-plugin .captcha-trigger.is-retry .trigger-action-text {
  color: rgb(185 28 28);
}

.slider-captcha-plugin .captcha-trigger.is-solved .trigger-meta,
.slider-captcha-plugin .captcha-trigger.is-solved .trigger-action-text {
  color: rgb(5 150 105);
}

.captcha-floating-layer {
  position: fixed;
  inset: 0;
  z-index: 2400;
  background: transparent;
}

.captcha-floating-layer .captcha-modal-panel {
  position: fixed;
  border: 1px solid var(--captcha-border);
  border-radius: 18px;
  padding: 20px;
  background: var(--captcha-surface);
  box-shadow: var(--captcha-shadow);
  animation: modal-rise 0.18s ease;
  overflow: visible;
}

.captcha-floating-layer .panel-caret {
  position: absolute;
  top: -7px;
  left: calc(var(--panel-caret-left, 48px) - 7px);
  width: 14px;
  height: 14px;
  border-top: 1px solid var(--captcha-border);
  border-left: 1px solid var(--captcha-border);
  background: var(--captcha-surface);
  transform: rotate(45deg);
}

.captcha-floating-layer .captcha-modal-panel[data-placement='top'] .panel-caret {
  top: auto;
  bottom: -7px;
  border-top: none;
  border-left: none;
  border-right: 1px solid var(--captcha-border);
  border-bottom: 1px solid var(--captcha-border);
}

.captcha-floating-layer .modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.captcha-floating-layer .modal-title-group {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.captcha-floating-layer .modal-title {
  margin: 0;
  color: var(--captcha-text);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: -0.01em;
}

.captcha-floating-layer .modal-subtitle {
  margin: 5px 0 0;
  color: var(--captcha-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.captcha-floating-layer .modal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.captcha-floating-layer .modal-refresh {
  height: 28px;
  padding: 0 4px;
  border: none;
  background: transparent;
  color: rgb(71 85 105);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

.captcha-floating-layer .modal-refresh:hover:not(:disabled) {
  color: rgb(30 41 59);
}

.captcha-floating-layer .modal-refresh:disabled,
.captcha-floating-layer .modal-close-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.captcha-floating-layer .modal-close-button {
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

.captcha-floating-layer .modal-close-button:hover {
  background: rgb(248 250 252);
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
  content: '';
  position: absolute;
  top: 6px;
  left: 1px;
  width: 12px;
  height: 1.5px;
  border-radius: 999px;
  background: rgb(100 116 139);
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
  gap: 12px;
}

.captcha-floating-layer .board-host {
  width: 100%;
  display: flex;
  justify-content: center;
}

.captcha-floating-layer .captcha-board {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--captcha-border);
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(248 250 252), rgb(241 245 249));
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.72);
}

.captcha-floating-layer .captcha-board.is-solved::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgb(16 185 129 / 0.02), rgb(16 185 129 / 0.08));
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
  font-weight: 500;
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
  filter:
    drop-shadow(0 0 1px rgb(255 255 255 / 0.9))
    drop-shadow(0 10px 16px rgb(15 23 42 / 0.24));
  transition:
    left 0.14s ease,
    top 0.14s ease,
    filter 0.14s ease;
  will-change: left;
}

.captcha-floating-layer .piece-canvas.is-dragging {
  filter:
    drop-shadow(0 1px 0 rgb(255 255 255 / 0.92))
    drop-shadow(0 14px 20px rgb(15 23 42 / 0.24));
  transition: none;
}

.captcha-floating-layer .piece-canvas.is-solved {
  filter:
    drop-shadow(0 1px 0 rgb(255 255 255 / 0.94))
    drop-shadow(0 10px 18px rgb(22 163 74 / 0.18));
}

.captcha-floating-layer .board-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: rgb(255 255 255 / 0.74);
  color: var(--captcha-text);
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(6px);
}

.captcha-floating-layer .loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--captcha-accent);
  box-shadow: 0 0 0 5px rgb(219 234 254);
  animation: pulse-dot 1s ease-in-out infinite;
}

.captcha-floating-layer .slider-track {
  position: relative;
  height: 48px;
  overflow: hidden;
  border: 1px solid rgb(225 231 239);
  border-radius: 14px;
  background: linear-gradient(180deg, rgb(247 249 252), rgb(238 243 248));
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.86),
    inset 0 -1px 0 rgb(226 232 240 / 0.68);
}

.captcha-floating-layer .slider-track::after {
  content: '';
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
  background: linear-gradient(90deg, rgb(219 234 254 / 0.78), rgb(191 219 254 / 0.46));
  box-shadow: inset 0 0 0 1px rgb(191 219 254 / 0.18);
  transition: width 0.14s ease;
}

.captcha-floating-layer .track-copy {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 72px;
  color: rgb(100 116 139);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.01em;
  pointer-events: none;
  user-select: none;
  white-space: nowrap;
}

.captcha-floating-layer .slider-thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  border: 1px solid rgb(213 221 233 / 0.96);
  border-radius: 12px;
  background: linear-gradient(180deg, rgb(255 255 255), rgb(246 249 252));
  box-shadow:
    0 6px 16px rgb(15 23 42 / 0.12),
    0 1px 3px rgb(15 23 42 / 0.06),
    inset 0 1px 0 rgb(255 255 255 / 0.94);
  cursor: grab;
  transition:
    transform 0.14s ease,
    box-shadow 0.14s ease,
    border-color 0.14s ease;
}

.captcha-floating-layer .slider-thumb:hover:not(:disabled) {
  border-color: rgb(191 219 254);
}

.captcha-floating-layer .slider-thumb.is-dragging {
  cursor: grabbing;
  transform: translateY(-1px);
  box-shadow:
    0 10px 20px rgb(37 99 235 / 0.16),
    0 3px 8px rgb(15 23 42 / 0.08),
    inset 0 1px 0 rgb(255 255 255 / 0.96);
}

.captcha-floating-layer .slider-thumb.is-solved {
  background: rgb(236 253 245);
  border-color: rgb(167 243 208);
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
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  margin-top: -3px;
  margin-left: -6px;
  border-top: 2px solid var(--captcha-accent);
  border-right: 2px solid var(--captcha-accent);
  transform: rotate(45deg);
}

.captcha-floating-layer .thumb-core::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  margin-top: -3px;
  margin-left: 1px;
  border-top: 2px solid var(--captcha-accent);
  border-right: 2px solid var(--captcha-accent);
  transform: rotate(45deg);
}

.captcha-floating-layer .slider-note {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--captcha-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.captcha-floating-layer .slider-note-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgb(148 163 184);
  flex: none;
}

.captcha-floating-layer .slider-note[data-state='retry'] .slider-note-dot {
  background: rgb(239 68 68);
}

.captcha-floating-layer .slider-note[data-state='success'] .slider-note-dot {
  background: rgb(34 197 94);
}

.captcha-floating-layer .slider-note[data-state='loading'] .slider-note-dot {
  background: var(--captcha-accent);
}

.captcha-floating-layer .slider-note[data-state='retry'] {
  color: rgb(185 28 28);
}

.captcha-floating-layer .slider-note[data-state='success'] {
  color: rgb(22 101 52);
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

@keyframes solved-sheen {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
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
    min-height: 46px;
    padding-right: 12px;
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
    padding: 0 64px;
  }
}
</style>
