/**
 * Dashboard widget layout.
 */
export const WX_DASHBOARD = `
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
`;
