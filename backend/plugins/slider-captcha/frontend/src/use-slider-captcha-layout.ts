import { computed, type Ref } from "vue";

import {
  getSliderCaptchaDisplayWidth,
  resolveSliderCaptchaModalLayout,
  type SliderCaptchaModalPlacement,
  type SliderCaptchaModalPosition,
} from "./slider-captcha-modal-helpers";

type ChallengePayload = {
  canvas_height: number;
  canvas_width: number;
  piece_height: number;
  piece_top: number;
  piece_width: number;
};

type UseSliderCaptchaLayoutParams = {
  boardHostRef: Ref<HTMLElement | null>;
  challenge: Ref<ChallengePayload | null>;
  displayWidth: Ref<number>;
  dragX: Ref<number>;
  modalPanelRef: Ref<HTMLElement | null>;
  modalPlacement: Ref<SliderCaptchaModalPlacement>;
  modalPosition: Ref<SliderCaptchaModalPosition>;
  solved: Ref<boolean>;
  solvedOffset: Ref<null | number>;
  triggerButtonRef: Ref<HTMLElement | null>;
};

export function useSliderCaptchaLayout(params: UseSliderCaptchaLayoutParams) {
  const boardWidth = computed(() => {
    if (!params.challenge.value) {
      return 320;
    }
    return Math.min(params.displayWidth.value, params.challenge.value.canvas_width);
  });

  const scaleRatio = computed(() => {
    if (!params.challenge.value) {
      return 1;
    }
    return boardWidth.value / params.challenge.value.canvas_width;
  });

  const boardHeight = computed(() => {
    if (!params.challenge.value) {
      return 180;
    }
    return params.challenge.value.canvas_height * scaleRatio.value;
  });

  const pieceLength = computed(() => {
    if (!params.challenge.value) {
      return 0;
    }
    return params.challenge.value.piece_width;
  });

  const pieceTravelMax = computed(() => {
    if (!params.challenge.value) {
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
    return (params.dragX.value / pieceTravelMax.value) * handleTravelMax.value;
  });

  const pieceStyle = computed(() => {
    if (!params.challenge.value) {
      return {
        height: "0px",
        left: "0px",
        top: "0px",
        width: "0px",
      };
    }
    const pieceTop = params.challenge.value.piece_top * scaleRatio.value;
    const pieceHeight = params.challenge.value.piece_height * scaleRatio.value;
    const pieceWidth = params.challenge.value.piece_width * scaleRatio.value;
    return {
      height: `${pieceHeight}px`,
      left: `${params.dragX.value}px`,
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
      "--panel-caret-left": `${params.modalPosition.value.caretLeft}px`,
      left: `${params.modalPosition.value.left}px`,
      top: `${params.modalPosition.value.top}px`,
      width: `${params.modalPosition.value.width}px`,
    } as Record<string, string>;
  });

  function updateDisplayWidth(): void {
    params.displayWidth.value = getSliderCaptchaDisplayWidth(
      params.boardHostRef.value?.clientWidth,
    );
  }

  function updateModalPosition(): void {
    const triggerEl = params.triggerButtonRef.value;
    if (!triggerEl) {
      return;
    }
    const { placement, position } = resolveSliderCaptchaModalLayout(
      triggerEl.getBoundingClientRect(),
      {
        modalHeight: params.modalPanelRef.value?.offsetHeight ?? 336,
      },
    );
    params.modalPlacement.value = placement;
    params.modalPosition.value = position;
  }

  function setPieceLeft(pieceLeft: number): void {
    params.dragX.value = Math.min(
      pieceTravelMax.value,
      Math.max(0, pieceLeft * scaleRatio.value),
    );
  }

  function setHandlePosition(nextHandle: number): void {
    if (!handleTravelMax.value || !pieceTravelMax.value) {
      params.dragX.value = 0;
      return;
    }
    const clampedHandle = Math.max(
      0,
      Math.min(handleTravelMax.value, nextHandle),
    );
    params.dragX.value =
      (clampedHandle / handleTravelMax.value) * pieceTravelMax.value;
  }

  function syncDragAfterResize(previousScale: number): void {
    if (!params.challenge.value || previousScale <= 0) {
      return;
    }
    const pieceLeft = params.solved.value
      ? (params.solvedOffset.value ?? params.dragX.value / previousScale)
      : params.dragX.value / previousScale;
    setPieceLeft(pieceLeft);
  }

  return {
    boardHeight,
    boardStyle,
    boardWidth,
    handleTravelMax,
    handleWidth,
    handleX,
    modalPanelStyle,
    pieceLength,
    pieceStyle,
    pieceTravelMax,
    scaleRatio,
    setHandlePosition,
    syncDragAfterResize,
    updateDisplayWidth,
    updateModalPosition,
  };
}
