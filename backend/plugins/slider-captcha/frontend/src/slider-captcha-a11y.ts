export type SliderThumbKeyboardAction =
  | "attempt"
  | "decrease"
  | "home"
  | "increase"
  | "none"
  | "to-end";

export function resolveSliderThumbKeyboardAction(
  event: KeyboardEvent,
): SliderThumbKeyboardAction {
  switch (event.key) {
    case "ArrowLeft":
      return "decrease";
    case "ArrowRight":
      return "increase";
    case "End":
      return "to-end";
    case "Home":
      return "home";
    case "Enter":
    case " ":
      return "attempt";
    default:
      return "none";
  }
}

interface WindowEventHandlers {
  onEscape: () => void;
  onResize: () => void;
  onScroll: () => void;
}

export function bindSliderCaptchaWindowEvents(
  handlers: WindowEventHandlers,
): () => void {
  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      handlers.onEscape();
    }
  };

  window.addEventListener("resize", handlers.onResize);
  window.addEventListener("scroll", handlers.onScroll, true);
  window.addEventListener("keydown", handleKeydown);

  return () => {
    window.removeEventListener("resize", handlers.onResize);
    window.removeEventListener("scroll", handlers.onScroll, true);
    window.removeEventListener("keydown", handleKeydown);
  };
}

