/**
 * Weather widget base tokens, layout, and effects.
 */
export const WX_BASE = `
.weather-popover-immersive-overlay {
  position: fixed;
  width: min(360px, calc(100vw - 20px));
  max-width: calc(100vw - 20px);
  z-index: 2400;
  pointer-events: auto;
  will-change: top, left;
}

.wx-panel,
.wx-dashboard {
  --wx-bg-top: #45617f;
  --wx-bg-bottom: #8da7c1;
  --wx-accent: rgba(255, 255, 255, 0.22);
  --wx-surface: rgba(255, 255, 255, 0.12);
  --wx-surface-strong: rgba(255, 255, 255, 0.18);
  --wx-outline: rgba(255, 255, 255, 0.14);
  --wx-outline-strong: rgba(255, 255, 255, 0.22);
  --wx-text-primary: #f8fbff;
  --wx-text-secondary: rgba(248, 251, 255, 0.76);
  --wx-text-faint: rgba(248, 251, 255, 0.54);
  --wx-shadow: 0 28px 68px rgba(15, 23, 42, 0.34);
  position: relative;
  overflow: hidden;
  color: var(--wx-text-primary);
  background: linear-gradient(155deg, var(--wx-bg-top), var(--wx-bg-bottom));
}

.wx-bg--clear-day {
  --wx-bg-top: #2962ef;
  --wx-bg-bottom: #70c0ff;
  --wx-accent: rgba(253, 224, 71, 0.28);
}

.wx-bg--clear-night {
  --wx-bg-top: #0b1634;
  --wx-bg-bottom: #1c396d;
  --wx-accent: rgba(226, 232, 240, 0.22);
}

.wx-bg--cloudy-day {
  --wx-bg-top: #3f5f80;
  --wx-bg-bottom: #8ea8c1;
  --wx-accent: rgba(255, 255, 255, 0.2);
}

.wx-bg--cloudy-night {
  --wx-bg-top: #1b2946;
  --wx-bg-bottom: #415d82;
  --wx-accent: rgba(203, 213, 225, 0.18);
}

.wx-bg--rain-day {
  --wx-bg-top: #334861;
  --wx-bg-bottom: #6b8cab;
  --wx-accent: rgba(125, 211, 252, 0.2);
}

.wx-bg--rain-night {
  --wx-bg-top: #0f1729;
  --wx-bg-bottom: #30445f;
  --wx-accent: rgba(125, 211, 252, 0.16);
}

.wx-bg--snow-day {
  --wx-bg-top: #6e86a3;
  --wx-bg-bottom: #c6d7ea;
  --wx-accent: rgba(255, 255, 255, 0.28);
}

.wx-bg--snow-night {
  --wx-bg-top: #1f2c42;
  --wx-bg-bottom: #576b87;
  --wx-accent: rgba(226, 232, 240, 0.18);
}

.wx-bg--thunder {
  --wx-bg-top: #111123;
  --wx-bg-bottom: #344069;
  --wx-accent: rgba(196, 181, 253, 0.22);
}

.wx-bg--fog {
  --wx-bg-top: #5e7898;
  --wx-bg-bottom: #bccddf;
  --wx-accent: rgba(255, 255, 255, 0.2);
}

.wx-panel::before,
.wx-dashboard::before {
  content: '';
  position: absolute;
  inset: auto -58px 52% auto;
  width: 188px;
  height: 188px;
  border-radius: 999px;
  background: radial-gradient(circle, var(--wx-accent) 0%, transparent 68%);
  filter: blur(2px);
  opacity: 0.92;
  pointer-events: none;
}

.wx-dashboard::before {
  inset: -28px -24px auto auto;
  width: 110px;
  height: 110px;
  filter: blur(1px);
  opacity: 0.28;
}

.wx-panel__veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.08), rgba(8, 15, 28, 0.24)),
    radial-gradient(circle at 18% 20%, rgba(255, 255, 255, 0.1), transparent 38%);
  pointer-events: none;
}

.wx-dashboard .wx-panel__veil {
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.02), rgba(8, 15, 28, 0.14)),
    radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.04), transparent 32%);
}

.wx-panel__veil--dashboard {
  background:
    linear-gradient(180deg, rgba(10, 20, 40, 0.02), rgba(8, 15, 28, 0.12)),
    radial-gradient(circle at 16% 16%, rgba(255, 255, 255, 0.04), transparent 30%);
}

.wx-scene {
  position: absolute;
  inset: 54px 0 auto 0;
  height: 176px;
  pointer-events: none;
  overflow: hidden;
}

.wx-dashboard .wx-scene {
  inset: 10px 0 auto 0;
  height: 82px;
  opacity: 0.46;
}

.wx-scene__orb,
.wx-scene__cloud,
.wx-scene__spark,
.wx-scene__drop,
.wx-scene__flake,
.wx-scene__mist,
.wx-scene__flash {
  position: absolute;
  opacity: 0;
}

.wx-scene__orb {
  top: 6px;
  right: -10px;
  width: 100px;
  height: 100px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.56), rgba(255, 255, 255, 0.02) 68%);
  filter: blur(1px);
}

.wx-scene__cloud {
  width: 92px;
  height: 30px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.02));
  filter: blur(2px);
}

.wx-scene__cloud--1 {
  top: 28px;
  right: 42px;
}

.wx-scene__cloud--2 {
  top: 62px;
  right: 88px;
  width: 68px;
  height: 22px;
}

.wx-scene__spark {
  width: 3px;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
}

.wx-scene__spark--1 {
  top: 20px;
  right: 118px;
}

.wx-scene__spark--2 {
  top: 54px;
  right: 150px;
}

.wx-scene__spark--3 {
  top: 34px;
  right: 72px;
}

.wx-scene__drop {
  top: 42px;
  right: 78px;
  width: 2px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(186, 230, 253, 0.6));
}

.wx-scene__drop--2 {
  right: 96px;
  height: 11px;
}

.wx-scene__drop--3 {
  right: 114px;
  height: 16px;
}

.wx-scene__flake {
  top: 42px;
  right: 90px;
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
}

.wx-scene__flake--2 {
  top: 92px;
  right: 118px;
  width: 3px;
  height: 3px;
}

.wx-scene__mist {
  left: -15%;
  width: 140%;
  height: 34px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  filter: blur(14px);
}

.wx-scene__mist--1 {
  top: 40px;
}

.wx-scene__mist--2 {
  top: 78px;
}

.wx-scene__flash {
  inset: 0;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.08);
}

.wx-noise::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 148px 148px;
  opacity: 0.04;
  pointer-events: none;
}

.wx-dashboard.wx-noise::after {
  opacity: 0.016;
}

.wx-fade-slide-enter-active,
.wx-fade-slide-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
}

.wx-fade-slide-enter-from,
.wx-fade-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
`;
