/**
 * Responsive and reduced-motion tweaks.
 */
export const WX_RESPONSIVE = `
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
