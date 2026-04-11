/**
 * Header trigger styles.
 */
export const WX_TRIGGER = `
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
`;
