/**
 * Skeleton and empty state styles.
 */
export const WX_SKELETON = `
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
`;
