/**
 * Weather widget design tokens and shared styles.
 *
 * Styles are injected through JS because popover content is rendered in a portal.
 */
export const WX_STYLES = `
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

.wx-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  border: none;
  background: transparent;
  color: rgb(71, 85, 105);
  border-radius: 999px;
  padding: 4px 8px;
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}

.wx-trigger:hover {
  background: rgba(15, 23, 42, 0.06);
  transform: none;
}

.wx-trigger__icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  height: auto;
  border-radius: 0;
  background: transparent;
}

.wx-trigger__icon {
  width: 16px;
  height: 16px;
  color: currentColor;
}

.wx-trigger__copy {
  display: none;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.05;
}

.wx-trigger__copy small {
  max-width: 88px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(100, 116, 139);
  font-size: 10px;
}

.wx-trigger__copy strong {
  font-size: 13px;
  font-weight: 700;
  color: rgb(30, 41, 59);
}

@media (min-width: 640px) {
  .wx-trigger__copy {
    display: flex;
  }
}

.wx-panel {
  width: min(360px, calc(100vw - 20px));
  border-radius: 24px;
  box-shadow: var(--wx-shadow);
  will-change: transform;
}

.wx-city-panel,
.wx-main-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  max-height: min(70vh, 520px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.18) transparent;
}

.wx-city-panel::-webkit-scrollbar,
.wx-main-panel::-webkit-scrollbar {
  width: 6px;
}

.wx-city-panel::-webkit-scrollbar-thumb,
.wx-main-panel::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.16);
  border-radius: 999px;
}

.wx-city-panel__head,
.wx-main-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.wx-city-panel__head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.wx-city-panel__summary {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--wx-outline);
  background: var(--wx-surface);
  backdrop-filter: blur(18px);
}

.wx-city-panel__label {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.08);
  color: var(--wx-text-primary);
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    transform 0.2s ease;
}

.wx-icon-btn:hover,
.wx-city-btn:hover,
.wx-locate-btn:hover,
.wx-action-btn:hover,
.wx-city-chip:hover {
  transform: translateY(-1px);
}

.wx-icon-btn:hover,
.wx-city-btn:hover,
.wx-locate-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  border-color: var(--wx-outline-strong);
}

.wx-icon-btn:disabled,
.wx-locate-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  transform: none;
}

.wx-search {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 15px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(16px);
}

.wx-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--wx-text-primary);
  font-size: 14px;
}

.wx-search input::placeholder {
  color: var(--wx-text-faint);
}

.wx-city-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wx-state-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--wx-text-secondary);
  font-size: 12px;
}

.wx-state-line--error {
  background: rgba(248, 113, 113, 0.12);
  color: #fecaca;
}

.wx-locate-btn,
.wx-action-btn,
.wx-city-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--wx-outline);
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    transform 0.2s ease;
}

.wx-locate-btn {
  justify-content: center;
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.1);
  color: var(--wx-text-primary);
  font-weight: 600;
}

.wx-action-btn {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 999px;
  background: #ffffff;
  border-color: rgba(148, 163, 184, 0.24);
  color: rgb(15, 23, 42);
}

.wx-action-btn:hover {
  background: rgb(248, 250, 252);
}

.wx-city-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wx-city-group h4 {
  margin: 0;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-city-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-city-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 46px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.1);
  color: var(--wx-text-primary);
  text-align: left;
  transition:
    transform 0.2s ease,
    background 0.2s ease,
    border-color 0.2s ease;
}

.wx-city-chip:hover {
  background: rgba(255, 255, 255, 0.16);
  border-color: var(--wx-outline);
}

.wx-city-chip__main {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  font-weight: 600;
}

.wx-city-chip__meta {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-city-btn {
  min-height: 34px;
  max-width: 100%;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: var(--wx-text-primary);
  min-width: 0;
}

.wx-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wx-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(7, 14, 28, 0.18);
  color: var(--wx-text-secondary);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.wx-hero {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 0 0;
}

.wx-hero__eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--wx-text-faint);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.wx-hero__body {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.wx-hero__copy {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.wx-hero__temp {
  font-size: 52px;
  line-height: 0.92;
  letter-spacing: -0.06em;
  font-weight: 200;
}

.wx-hero__text {
  font-size: 14px;
  font-weight: 700;
}

.wx-hero__sub {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 11px;
  color: var(--wx-text-secondary);
}

.wx-hero__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.wx-hero__icon-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(18px);
}

.wx-hero__icon {
  width: 46px;
  height: 46px;
  filter: drop-shadow(0 16px 22px rgba(8, 15, 30, 0.18));
}

.wx-hero__unit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(7, 14, 28, 0.18);
  color: var(--wx-text-secondary);
  font-size: 12px;
}

.wx-stale-badge {
  padding: 6px 9px;
  border-radius: 12px;
  border: 1px solid rgba(250, 204, 21, 0.24);
  background: rgba(250, 204, 21, 0.16);
  color: #fef3c7;
  font-size: 12px;
}

.wx-chip-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-chip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 60px;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.07));
  backdrop-filter: blur(18px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.wx-chip span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-chip strong {
  font-size: 15px;
  line-height: 1.1;
  font-weight: 700;
}

.wx-chip small {
  font-size: 10px;
  color: var(--wx-text-secondary);
}

.wx-hourly-band,
.wx-forecast-sheet {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0 0;
}

.wx-section-head--inline {
  padding: 0 4px;
}

.wx-hourly-scroll {
  gap: 12px;
  padding: 8px 0 6px;
}

.wx-hour-item {
  flex: 0 0 66px;
  padding: 12px 8px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.06));
  backdrop-filter: blur(18px);
}

.wx-hour-item--active {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.08));
}

.wx-sun-strip {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-sun-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(7, 14, 28, 0.16);
  backdrop-filter: blur(14px);
}

.wx-sun-chip span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-sun-chip strong {
  font-size: 13px;
  font-weight: 700;
}

.wx-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 22px;
  border: 1px solid var(--wx-outline);
  background: var(--wx-surface);
  backdrop-filter: blur(18px) saturate(1.2);
}

.wx-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.wx-section-head h4 {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
}

.wx-section-head span {
  font-size: 10px;
  color: var(--wx-text-faint);
}

.wx-hourly-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  scrollbar-width: none;
  padding-bottom: 2px;
}

.wx-hourly-scroll::-webkit-scrollbar {
  display: none;
}

.wx-hour-item {
  flex: 0 0 54px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 9px 6px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid transparent;
  color: var(--wx-text-secondary);
}

.wx-hour-item--active {
  background: rgba(255, 255, 255, 0.18);
  border-color: var(--wx-outline-strong);
  color: var(--wx-text-primary);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
}

.wx-hour-item__time {
  font-size: 10px;
}

.wx-hour-item__temp {
  font-size: 12px;
  font-weight: 700;
  color: var(--wx-text-primary);
}

.wx-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.wx-metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 90px;
  padding: 14px 14px 12px;
  border-radius: 20px;
  border: 1px solid var(--wx-outline);
  background: rgba(255, 255, 255, 0.09);
  backdrop-filter: blur(16px);
}

.wx-metric span {
  font-size: 12px;
  color: var(--wx-text-faint);
}

.wx-metric strong {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
}

.wx-metric small {
  font-size: 12px;
  color: var(--wx-text-secondary);
}

.wx-forecast {
  gap: 10px;
}

.wx-forecast-row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) auto minmax(0, 0.9fr);
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.wx-forecast-row:first-of-type {
  padding-top: 0;
  border-top: none;
}

.wx-forecast-row__day {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.wx-forecast-row__day span {
  font-size: 12px;
  font-weight: 600;
}

.wx-forecast-row__day small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
  color: var(--wx-text-faint);
}

.wx-forecast-row__temp {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  font-size: 10px;
  color: var(--wx-text-secondary);
}

.wx-forecast-row__temp span:first-child {
  color: var(--wx-text-primary);
  font-weight: 600;
}

.wx-skeleton-wrap,
.wx-dashboard-skeleton {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.wx-dashboard-skeleton__row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.wx-skeleton {
  border-radius: 18px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.08) 20%,
    rgba(255, 255, 255, 0.18) 50%,
    rgba(255, 255, 255, 0.08) 80%
  );
  background-size: 200% 100%;
  animation: wx-shimmer 1.6s linear infinite;
}

.wx-skeleton--lg {
  min-height: 136px;
}

.wx-skeleton--md {
  min-height: 72px;
}

.wx-skeleton--grid {
  min-height: 160px;
}

.wx-skeleton--tile {
  min-height: 88px;
}

@keyframes wx-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.wx-empty,
.wx-dashboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 260px;
  padding: 20px;
  border-radius: 22px;
  border: 1px dashed rgba(148, 163, 184, 0.24);
  background: rgba(248, 250, 252, 0.68);
  text-align: center;
}

.wx-empty p,
.wx-dashboard-empty__desc {
  margin: 0;
  font-size: 12px;
  color: rgb(100, 116, 139);
}

.wx-dashboard-empty__title {
  font-size: 14px;
  font-weight: 700;
  color: rgb(15, 23, 42);
}

.wx-dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.wx-dashboard {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: auto;
  min-height: 0;
  padding: 12px;
  border-radius: 18px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.14);
}

.wx-dashboard__topbar,
.wx-dashboard__hero,
.wx-dashboard__chip-row,
.wx-dashboard__forecast-ribbon {
  position: relative;
  z-index: 1;
}

.wx-dashboard__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.wx-dashboard__topbar .wx-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(6px);
}

.wx-dashboard__hero {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.wx-dashboard__eyebrow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  min-width: 0;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-dashboard__eyebrow span:first-child {
  max-width: min(100%, 180px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--wx-text-primary);
}

.wx-dashboard__eyebrow span:last-child {
  color: var(--wx-text-secondary);
}

.wx-dashboard__hero-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: end;
  gap: 12px;
  min-width: 0;
}

.wx-dashboard__temp {
  font-size: 46px;
  line-height: 0.86;
  letter-spacing: -0.05em;
  font-weight: 220;
  flex-shrink: 0;
}

.wx-dashboard__condition-wrap {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 5px;
  min-width: 0;
  padding-bottom: 2px;
}

.wx-dashboard__condition-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.wx-dashboard__condition {
  font-size: 14px;
  line-height: 1.2;
  font-weight: 700;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 10px;
  font-size: 11px;
  line-height: 1.25;
  color: var(--wx-text-secondary);
}

.wx-dashboard__meta span {
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(6px);
  flex-shrink: 0;
}

.wx-dashboard__icon {
  width: 18px;
  height: 18px;
}

.wx-dashboard__chip-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wx-dashboard__chip {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  min-height: 50px;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
}

.wx-dashboard__chip span {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--wx-text-faint);
}

.wx-dashboard__chip strong {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__chip small {
  font-size: 10px;
  line-height: 1.2;
  color: var(--wx-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__chip--wide {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'label value'
    'note value';
  align-items: center;
  gap: 10px;
  min-height: 50px;
}

.wx-dashboard__chip--wide span {
  grid-area: label;
}

.wx-dashboard__chip--wide strong {
  grid-area: value;
  font-size: 18px;
}

.wx-dashboard__chip--wide small {
  grid-area: note;
}

.wx-dashboard__forecast-ribbon {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.wx-dashboard__forecast-pill {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  min-width: 0;
  padding: 7px 9px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(7, 14, 28, 0.1);
  backdrop-filter: blur(6px);
}

.wx-dashboard__forecast-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  font-size: 10px;
  font-weight: 700;
}

.wx-dashboard__forecast-text {
  min-height: 0;
  font-size: 10px;
  line-height: 1.2;
  color: var(--wx-text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wx-dashboard__forecast-range {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
}

.wx-dashboard__forecast-range span:first-child {
  font-weight: 700;
}

.wx-dashboard__forecast-range span:last-child {
  color: var(--wx-text-secondary);
}

.wx-scene--sun .wx-scene__orb,
.wx-scene--moon-star .wx-scene__orb,
.wx-scene--cloud .wx-scene__cloud,
.wx-scene--rain .wx-scene__cloud,
.wx-scene--snow .wx-scene__cloud,
.wx-scene--moon-star .wx-scene__spark,
.wx-scene--rain .wx-scene__drop,
.wx-scene--snow .wx-scene__flake,
.wx-scene--fog .wx-scene__mist,
.wx-scene--thunder .wx-scene__flash {
  opacity: 1;
}

.wx-scene--sun .wx-scene__orb {
  background: radial-gradient(circle, rgba(253, 224, 71, 0.8), rgba(251, 191, 36, 0.08) 70%);
  box-shadow: 0 0 80px rgba(253, 224, 71, 0.22);
  animation: wx-sun-pulse 7s ease-in-out infinite;
}

.wx-scene--moon-star .wx-scene__orb {
  width: 108px;
  height: 108px;
  background: radial-gradient(circle, rgba(226, 232, 240, 0.5), rgba(226, 232, 240, 0.04) 70%);
  box-shadow: 0 0 60px rgba(226, 232, 240, 0.12);
}

.wx-scene--cloud .wx-scene__cloud,
.wx-scene--rain .wx-scene__cloud,
.wx-scene--snow .wx-scene__cloud {
  animation: wx-cloud-float 12s ease-in-out infinite;
}

.wx-scene--moon-star .wx-scene__spark {
  animation: wx-sparkle 2.8s ease-in-out infinite;
}

.wx-scene--rain .wx-scene__drop {
  animation: wx-rain-fall 1.6s linear infinite;
}

.wx-scene--snow .wx-scene__flake {
  animation: wx-snow-drift 3.6s ease-in-out infinite;
}

.wx-scene--fog .wx-scene__mist {
  animation: wx-mist-drift 14s ease-in-out infinite;
}

.wx-scene--thunder .wx-scene__flash {
  animation: wx-thunder-flash 4.8s ease-in-out infinite;
}

@keyframes wx-sun-pulse {
  0%,
  100% {
    transform: scale(0.96);
    opacity: 0.76;
  }
  50% {
    transform: scale(1.06);
    opacity: 1;
  }
}

@keyframes wx-cloud-float {
  0%,
  100% {
    transform: translateX(0) translateY(0);
  }
  50% {
    transform: translateX(8px) translateY(-4px);
  }
}

@keyframes wx-sparkle {
  0%,
  100% {
    transform: scale(0.8);
    opacity: 0.18;
  }
  50% {
    transform: scale(1.25);
    opacity: 1;
  }
}

@keyframes wx-rain-fall {
  0% {
    transform: translateY(-6px);
    opacity: 0;
  }
  25% {
    opacity: 0.85;
  }
  100% {
    transform: translateY(40px);
    opacity: 0;
  }
}

@keyframes wx-snow-drift {
  0% {
    transform: translateY(-4px) translateX(0) scale(0.8);
    opacity: 0;
  }
  30% {
    opacity: 0.92;
  }
  100% {
    transform: translateY(38px) translateX(10px) scale(1.05);
    opacity: 0;
  }
}

@keyframes wx-mist-drift {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(24px);
  }
}

@keyframes wx-thunder-flash {
  0%,
  90%,
  100% {
    opacity: 0;
  }
  92% {
    opacity: 0.75;
  }
  94% {
    opacity: 0.1;
  }
  96% {
    opacity: 0.35;
  }
}

@media (max-width: 480px) {
  .wx-city-grid {
    grid-template-columns: 1fr;
  }

  .wx-city-panel,
  .wx-main-panel,
  .wx-dashboard {
    padding: 10px;
  }

  .wx-hero__body {
    flex-direction: column;
    align-items: flex-start;
  }

  .wx-hero__meta {
    align-items: flex-end;
  }

  .wx-hero__temp,
  .wx-dashboard__temp {
    font-size: 40px;
  }

  .wx-dashboard {
    gap: 9px;
    border-radius: 16px;
  }

  .wx-dashboard__topbar {
    gap: 8px;
  }

  .wx-dashboard__eyebrow span:first-child {
    max-width: 132px;
  }

  .wx-dashboard__hero {
    gap: 0;
  }

  .wx-dashboard__hero-main {
    gap: 8px;
  }

  .wx-dashboard__condition-line {
    gap: 6px;
  }

  .wx-dashboard__condition {
    font-size: 14px;
  }

  .wx-dashboard__chip-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wx-dashboard__chip--wide {
    grid-column: 1 / -1;
  }

  .wx-chip-grid,
  .wx-sun-strip {
    grid-template-columns: 1fr;
  }

  .wx-dashboard__forecast-ribbon {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 5px;
  }

  .wx-dashboard__forecast-pill {
    padding: 7px 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .wx-panel *,
  .wx-dashboard *,
  .wx-trigger {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}
`;
