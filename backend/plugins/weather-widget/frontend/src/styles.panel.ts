/**
 * Popover panel, hero, and forecast layout styles.
 */
export const WX_PANEL = `
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

.wx-forecast-row__temp span:last-child {
  color: var(--wx-text-secondary);
}
`;
