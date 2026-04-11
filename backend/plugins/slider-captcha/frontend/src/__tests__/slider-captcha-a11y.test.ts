import { describe, expect, it, vi } from "vitest";

import {
  bindSliderCaptchaWindowEvents,
  resolveSliderThumbKeyboardAction,
} from "../slider-captcha-a11y";

describe("slider-captcha-a11y", () => {
  it.each([
    ["ArrowLeft", "decrease"],
    ["ArrowRight", "increase"],
    ["End", "to-end"],
    ["Home", "home"],
    ["Enter", "attempt"],
    [" ", "attempt"],
    ["Tab", "none"],
  ])("maps %s to %s", (key, action) => {
    expect(
      resolveSliderThumbKeyboardAction(
        new KeyboardEvent("keydown", { key }),
      ),
    ).toBe(action);
  });

  it("binds and unbinds global escape, resize, and scroll handlers", () => {
    const onEscape = vi.fn();
    const onResize = vi.fn();
    const onScroll = vi.fn();

    const unbind = bindSliderCaptchaWindowEvents({
      onEscape,
      onResize,
      onScroll,
    });

    window.dispatchEvent(new Event("resize"));
    window.dispatchEvent(new Event("scroll"));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(onResize).toHaveBeenCalledTimes(1);
    expect(onScroll).toHaveBeenCalledTimes(1);
    expect(onEscape).toHaveBeenCalledTimes(1);

    unbind();

    window.dispatchEvent(new Event("resize"));
    window.dispatchEvent(new Event("scroll"));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(onResize).toHaveBeenCalledTimes(1);
    expect(onScroll).toHaveBeenCalledTimes(1);
    expect(onEscape).toHaveBeenCalledTimes(1);
  });
});
