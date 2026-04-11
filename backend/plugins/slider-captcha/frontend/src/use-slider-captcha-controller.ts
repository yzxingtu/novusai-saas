import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import {
  bindSliderCaptchaWindowEvents,
  resolveSliderThumbKeyboardAction,
} from "./slider-captcha-a11y";
import {
  type SliderCaptchaModalPlacement,
  type SliderCaptchaModalPosition,
} from "./slider-captcha-modal-helpers";
import { getSliderCaptchaShared } from "./slider-captcha-shared";
import { createSliderCaptchaStateMachine } from "./slider-captcha-state-machine";
import { useSliderCaptchaChallenge } from "./use-slider-captcha-challenge";
import { useSliderCaptchaLayout } from "./use-slider-captcha-layout";

import type { SliderCaptchaResult } from "./types";

type UseSliderCaptchaControllerOptions = {
  action: () => string;
  difficulty: () => "easy" | "hard" | "medium";
  disabled: () => boolean;
  endpoint: () => string;
  onError: (error: Error) => void;
  onVerified: (result: SliderCaptchaResult) => void;
};

export function useSliderCaptchaController(
  options: UseSliderCaptchaControllerOptions,
) {
  const triggerButtonRef = ref<HTMLElement | null>(null);
  const modalPanelRef = ref<HTMLElement | null>(null);
  const boardHostRef = ref<HTMLElement | null>(null);
  const boardCanvasRef = ref<HTMLCanvasElement | null>(null);
  const pieceCanvasRef = ref<HTMLCanvasElement | null>(null);

  const dragX = ref(0);
  const solved = ref(false);
  const solvedOffset = ref<null | number>(null);
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
  let layout!: ReturnType<typeof useSliderCaptchaLayout>;

  function clearWindowDragListeners(): void {
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", handlePointerUp);
    window.removeEventListener("pointercancel", handlePointerUp);
  }

  function releaseDrag(): void {
    pointerId = null;
    dragging.value = false;
    clearWindowDragListeners();
  }

  const challengeState = useSliderCaptchaChallenge(
    () => getSliderCaptchaShared()?.requestClient,
    {
      action: options.action,
      boardCanvasRef,
      difficulty: options.difficulty,
      dragX,
      endpoint: options.endpoint,
      getScaleRatio: () => layout.scaleRatio.value,
      modalVisible,
      pieceCanvasRef,
      releaseDrag,
      solved,
      solvedOffset,
      syncDragAfterResize: (previousScale) =>
        layout.syncDragAfterResize(previousScale),
      updateDisplayWidth: () => layout.updateDisplayWidth(),
      updateModalPosition: () => layout.updateModalPosition(),
    },
  );

  layout = useSliderCaptchaLayout({
    boardHostRef,
    challenge: challengeState.challenge,
    displayWidth,
    dragX,
    modalPanelRef,
    modalPlacement,
    modalPosition,
    solved,
    solvedOffset,
    triggerButtonRef,
  });

  const progressPercent = computed(() => {
    if (!layout.handleTravelMax.value) {
      return solved.value ? 100 : 0;
    }
    return Math.round(
      (layout.handleX.value / layout.handleTravelMax.value) * 100,
    );
  });

  const stateMachine = createSliderCaptchaStateMachine({
    challenge: challengeState.challenge,
    challengeId: challengeState.challengeId,
    detectedTargetLeft: challengeState.detectedTargetLeft,
    dragX,
    modalVisible,
    onRefresh: refresh,
    onVerified: options.onVerified,
    scaleRatio: () => layout.scaleRatio.value,
    solved,
    solvedOffset,
    statusKey: challengeState.statusKey,
  });

  function clearRetryTimer(): void {
    stateMachine.clearRetryTimer();
  }

  function clearSuccessCloseTimer(): void {
    stateMachine.clearSuccessCloseTimer();
  }

  function prepareInteraction(): void {
    stateMachine.prepareInteraction();
  }

  function setHandlePosition(nextHandle: number): void {
    layout.setHandlePosition(nextHandle);
  }

  function completeAttempt(): void {
    stateMachine.completeAttempt();
  }

  function handlePointerMove(event: PointerEvent): void {
    if (
      pointerId === null ||
      options.disabled() ||
      !challengeState.challenge.value
    ) {
      return;
    }

    const deltaX = event.clientX - pointerStartX;
    const nextHandle = Math.max(
      0,
      Math.min(layout.handleTravelMax.value, pointerStartHandleX + deltaX),
    );
    setHandlePosition(nextHandle);
  }

  function handlePointerUp(): void {
    const hasActiveDrag = pointerId !== null;
    releaseDrag();
    if (!challengeState.challenge.value || !hasActiveDrag) {
      return;
    }
    completeAttempt();
  }

  function handleThumbKeydown(event: KeyboardEvent): void {
    if (
      options.disabled() ||
      challengeState.loading.value ||
      !challengeState.challenge.value ||
      solved.value
    ) {
      return;
    }

    const step = Math.max(12, Math.round(layout.handleTravelMax.value / 10));

    switch (resolveSliderThumbKeyboardAction(event)) {
      case "decrease": {
        event.preventDefault();
        prepareInteraction();
        setHandlePosition(layout.handleX.value - step);
        return;
      }
      case "increase": {
        event.preventDefault();
        prepareInteraction();
        setHandlePosition(layout.handleX.value + step);
        return;
      }
      case "to-end": {
        event.preventDefault();
        prepareInteraction();
        setHandlePosition(layout.handleTravelMax.value);
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

  function addWindowDragListeners(): void {
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
  }

  function startDrag(event: PointerEvent): void {
    if (
      options.disabled() ||
      challengeState.loading.value ||
      !challengeState.challenge.value ||
      solved.value
    ) {
      return;
    }

    prepareInteraction();
    pointerId = event.pointerId;
    dragging.value = true;
    pointerStartX = event.clientX;
    pointerStartHandleX = layout.handleX.value;
    addWindowDragListeners();
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
    challengeState.resetChallengeState();
    modalVisible.value = false;
  }

  function refresh(): void {
    stateMachine.resetFailCounter();
    challengeState.resetChallengeState();
    if (modalVisible.value) {
      void safeLoadChallenge();
    }
  }

  function openModal(forceRefresh = false): void {
    if (options.disabled()) {
      return;
    }

    clearSuccessCloseTimer();
    stateMachine.resetFailCounter();
    if (forceRefresh) {
      if (modalVisible.value) {
        refresh();
        return;
      }
      challengeState.resetChallengeState();
    }
    modalVisible.value = true;
  }

  function handleTriggerClick(): void {
    if (options.disabled() || solved.value) {
      return;
    }
    openModal(
      challengeState.statusKey.value === "retry" ||
        !challengeState.challenge.value,
    );
  }

  function getResult(): null | SliderCaptchaResult {
    const result = stateMachine.getSolvedResult();
    if (!result) {
      openModal(
        challengeState.statusKey.value === "retry" ||
          !challengeState.challenge.value,
      );
      return null;
    }
    return result;
  }

  function handlePluginError(error: unknown): void {
    options.onError(error instanceof Error ? error : new Error(String(error)));
  }

  async function safeLoadChallenge(): Promise<void> {
    try {
      await challengeState.loadChallenge();
    } catch (error) {
      handlePluginError(error);
    }
  }

  async function safeRerenderChallenge(): Promise<void> {
    try {
      await challengeState.rerenderExistingChallenge();
    } catch (error) {
      challengeState.statusKey.value = "retry";
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
      layout.updateModalPosition();
    }
  }

  watch(
    () => [options.action(), options.endpoint()],
    () => {
      challengeState.resetChallengeState();
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
    layout.updateDisplayWidth();
    layout.updateModalPosition();
    if (!challengeState.challenge.value) {
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
    challengeState.resetChallengeState();
    modalVisible.value = false;
    releaseDrag();
    unbindWindowEvents?.();
    unbindWindowEvents = null;
  });

  return {
    boardCanvasRef,
    boardHostRef,
    challenge: challengeState.challenge,
    closeModal,
    dragging,
    getResult,
    handleThumbKeydown,
    handleTriggerClick,
    loading: challengeState.loading,
    modalPanelRef,
    modalPlacement,
    modalPanelStyle: layout.modalPanelStyle,
    modalVisible,
    pieceCanvasRef,
    pieceStyle: layout.pieceStyle,
    progressPercent,
    refresh,
    solved,
    startDrag,
    statusKey: challengeState.statusKey,
    triggerButtonRef,
    boardStyle: layout.boardStyle,
    handleWidth: layout.handleWidth,
    handleX: layout.handleX,
  };
}
