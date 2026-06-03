import { ref } from "vue";

import { beforeEach, describe, expect, it } from "vitest";

import { useSliderCaptchaLayout } from "../use-slider-captcha-layout";

import type {
  SliderCaptchaModalPlacement,
  SliderCaptchaModalPosition,
} from "../slider-captcha-modal-helpers";

function createChallenge() {
  return {
    canvas_height: 200,
    canvas_width: 400,
    piece_height: 60,
    piece_top: 30,
    piece_width: 50,
  };
}

function createLayout() {
  const displayWidth = ref(300);
  const dragX = ref(131.25);
  const modalPlacement = ref<SliderCaptchaModalPlacement>("top");
  const modalPosition = ref<SliderCaptchaModalPosition>({
    caretLeft: 48,
    left: 12,
    top: 12,
    width: 360,
  });
  const solved = ref(false);
  const solvedOffset = ref<number | null>(null);

  const boardHostRef = ref({
    clientWidth: 520,
  } as HTMLElement);
  const modalPanelRef = ref({
    offsetHeight: 280,
  } as HTMLElement);
  const triggerButtonRef = ref({
    getBoundingClientRect: () => new DOMRect(96, 10, 140, 40),
  } as HTMLElement);

  const layout = useSliderCaptchaLayout({
    boardHostRef,
    challenge: ref(createChallenge()),
    displayWidth,
    dragX,
    modalPanelRef,
    modalPlacement,
    modalPosition,
    solved,
    solvedOffset,
    triggerButtonRef,
  });

  return {
    boardHostRef,
    displayWidth,
    dragX,
    layout,
    modalPlacement,
    modalPosition,
    solved,
    solvedOffset,
  };
}

describe("use-slider-captcha-layout", () => {
  beforeEach(() => {
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 480,
    });
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 460,
    });
  });

  it("derives board geometry, handle travel, and clamped display widths", () => {
    const context = createLayout();

    expect(context.layout.boardWidth.value).toBe(300);
    expect(context.layout.boardHeight.value).toBe(150);
    expect(context.layout.scaleRatio.value).toBeCloseTo(0.75);
    expect(context.layout.pieceTravelMax.value).toBeCloseTo(262.5);
    expect(context.layout.handleWidth.value).toBe(45);
    expect(context.layout.handleTravelMax.value).toBe(255);
    expect(context.layout.handleX.value).toBeCloseTo(127.5);
    expect(context.layout.boardStyle.value).toEqual({
      height: "150px",
      width: "300px",
    });
    expect(context.layout.pieceStyle.value).toEqual({
      height: "45px",
      left: "131.25px",
      top: "22.5px",
      width: "37.5px",
    });

    context.layout.updateDisplayWidth();
    expect(context.displayWidth.value).toBe(300);

    context.boardHostRef.value = { clientWidth: 260 } as HTMLElement;
    context.layout.updateDisplayWidth();
    expect(context.displayWidth.value).toBe(280);
  });

  it("repositions the modal and resyncs solved drag offsets after resize", () => {
    const context = createLayout();

    context.layout.updateModalPosition();

    expect(context.modalPlacement.value).toBe("bottom");
    expect(context.modalPosition.value.left).toBe(12);
    expect(context.modalPosition.value.top).toBe(60);
    expect(context.modalPosition.value.width).toBe(312);
    expect(context.layout.modalPanelStyle.value).toEqual({
      "--panel-caret-left": "154px",
      left: "12px",
      top: "60px",
      width: "312px",
    });

    context.solved.value = true;
    context.solvedOffset.value = 120;
    context.dragX.value = 210;
    context.displayWidth.value = 280;

    context.layout.syncDragAfterResize(0.75);

    expect(context.dragX.value).toBeCloseTo(84);

    context.layout.setHandlePosition(999);
    expect(context.dragX.value).toBeCloseTo(context.layout.pieceTravelMax.value);
  });
});
