export type SliderCaptchaModalPlacement = "bottom" | "center" | "top";

export interface SliderCaptchaModalPosition {
  caretLeft: number;
  left: number;
  top: number;
  width: number;
}

export function getSliderCaptchaDisplayWidth(hostWidth?: number): number {
  const width = hostWidth ?? 320;
  return Math.max(280, Math.min(300, width));
}

interface ModalLayoutOptions {
  modalHeight?: number;
  panelGap?: number;
  viewportHeight?: number;
  viewportPadding?: number;
  viewportWidth?: number;
}

export function resolveSliderCaptchaModalLayout(
  triggerRect: DOMRect,
  options: ModalLayoutOptions = {},
): {
  placement: SliderCaptchaModalPlacement;
  position: SliderCaptchaModalPosition;
} {
  const viewportPadding = options.viewportPadding ?? 12;
  const panelGap = options.panelGap ?? 10;
  const viewportWidth = options.viewportWidth ?? window.innerWidth;
  const viewportHeight = options.viewportHeight ?? window.innerHeight;
  const panelHeight = options.modalHeight ?? 336;

  const preferredWidth = Math.max(312, Math.min(336, triggerRect.width + 8));
  const width = Math.min(
    preferredWidth,
    Math.max(280, viewportWidth - viewportPadding * 2),
  );
  const maxLeft = Math.max(viewportPadding, viewportWidth - viewportPadding - width);
  const left = Math.min(
    Math.max(
      viewportPadding,
      triggerRect.left + triggerRect.width / 2 - width / 2,
    ),
    maxLeft,
  );

  const topCandidate = triggerRect.top - panelHeight - panelGap;
  const bottomCandidate = triggerRect.bottom + panelGap;
  let placement: SliderCaptchaModalPlacement = "top";
  let top = topCandidate;

  if (topCandidate < viewportPadding) {
    if (bottomCandidate + panelHeight <= viewportHeight - viewportPadding) {
      placement = "bottom";
      top = bottomCandidate;
    } else {
      placement = "center";
      top = Math.max(
        viewportPadding,
        Math.round((viewportHeight - panelHeight) / 2),
      );
    }
  }

  const maxTop = Math.max(viewportPadding, viewportHeight - viewportPadding - panelHeight);
  const caretLeft = Math.min(
    Math.max(30, triggerRect.left + triggerRect.width / 2 - left),
    width - 30,
  );
  const centeredLeft = Math.min(
    Math.max(viewportPadding, Math.round((viewportWidth - width) / 2)),
    maxLeft,
  );

  return {
    placement,
    position: {
      caretLeft: placement === "center" ? width / 2 : caretLeft,
      left: placement === "center" ? centeredLeft : left,
      top: Math.min(Math.max(viewportPadding, top), maxTop),
      width,
    },
  };
}

