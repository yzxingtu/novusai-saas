/**
 * 天气插件全部样式（字符串形式）
 *
 * 因为 Ant Design Popover 在 portal 中渲染，Vue scoped CSS 的 data-v-xxx 不生效。
 * 所有样式通过 setup() 用 JS 注入到 <head>，以 .wx- 前缀避免冲突。
 */
export const WX_STYLES = `
/* ── Popover 覆盖 ── */
.weather-popover-immersive.ant-popover .ant-popover-inner {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: 0 12px 40px rgba(0,0,0,0.3) !important;
  border-radius: 16px !important;
  overflow: hidden !important;
}
.weather-popover-immersive.ant-popover .ant-popover-inner .ant-popover-inner-content {
  padding: 0 !important;
}
.weather-popover-immersive.ant-popover .ant-popover-arrow {
  display: none !important;
}

/* ── 触发按钮 ── */
.wx-trigger { display: flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.wx-trigger:hover { background: hsl(var(--accent)); }
.wx-trigger__temp { font-size: 13px; font-weight: 600; display: none; }
@media (min-width: 640px) { .wx-trigger__temp { display: inline; } }

/* ── 沉浸式面板 ── */
.wx-panel { position: relative; width: 340px; min-height: 360px; border-radius: 16px; overflow: hidden; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

/* ── 天气背景渐变 ── */
.wx-bg--clear-day { background: linear-gradient(165deg, #2196F3 0%, #64B5F6 40%, #90CAF9 100%); }
.wx-bg--clear-night { background: linear-gradient(165deg, #0D1B2A 0%, #1B2838 40%, #2C3E50 100%); }
.wx-bg--cloudy-day { background: linear-gradient(165deg, #546E7A 0%, #607D8B 40%, #78909C 100%); }
.wx-bg--cloudy-night { background: linear-gradient(165deg, #263238 0%, #37474F 40%, #455A64 100%); }
.wx-bg--rain-day { background: linear-gradient(165deg, #37474F 0%, #455A64 40%, #546E7A 100%); }
.wx-bg--rain-night { background: linear-gradient(165deg, #1A1A2E 0%, #16213E 40%, #0F3460 100%); }
.wx-bg--snow-day { background: linear-gradient(165deg, #78909C 0%, #90A4AE 50%, #B0BEC5 100%); }
.wx-bg--snow-night { background: linear-gradient(165deg, #37474F 0%, #455A64 50%, #546E7A 100%); }
.wx-bg--thunder { background: linear-gradient(165deg, #1A1A2E 0%, #2D132C 40%, #3E1F47 100%); }
.wx-bg--fog { background: linear-gradient(165deg, #78909C 0%, #90A4AE 50%, #B0BEC5 100%); }

/* ── 粒子层 ── */
.wx-particles { position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 1; }
.wx-rain { position: absolute; width: 1.5px; height: 16px; background: linear-gradient(180deg, transparent, rgba(255,255,255,0.5)); top: -20px; left: calc(var(--i) * 5%); animation: wx-rain-fall 0.7s linear infinite; animation-delay: calc(var(--i) * 0.05s); opacity: 0; }
@keyframes wx-rain-fall { 0% { opacity: 0; transform: translateY(0); } 15% { opacity: 0.7; } 100% { opacity: 0; transform: translateY(400px); } }
.wx-snow { position: absolute; width: 5px; height: 5px; background: rgba(255,255,255,0.8); border-radius: 50%; top: -10px; left: calc(var(--i) * 6.5%); animation: wx-snow-fall 3s ease-in-out infinite; animation-delay: calc(var(--i) * 0.2s); opacity: 0; }
@keyframes wx-snow-fall { 0% { opacity: 0; transform: translateY(0) translateX(0); } 15% { opacity: 0.9; } 100% { opacity: 0; transform: translateY(400px) translateX(20px); } }
.wx-cloud { position: absolute; width: 80px; height: 28px; background: rgba(255,255,255,0.15); border-radius: 28px; }
.wx-cloud::before, .wx-cloud::after { content: ''; position: absolute; background: inherit; border-radius: 50%; }
.wx-cloud::before { width: 36px; height: 36px; top: -20px; left: 12px; }
.wx-cloud::after { width: 26px; height: 26px; top: -12px; left: 40px; }
.wx-cloud--1 { top: 40px; left: -20px; animation: wx-cloud-drift 18s ease-in-out infinite; }
.wx-cloud--2 { top: 80px; right: -30px; animation: wx-cloud-drift 14s ease-in-out infinite reverse; opacity: 0.7; transform: scale(0.7); }
@keyframes wx-cloud-drift { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(60px); } }

/* ── 主视图 ── */
.wx-main { position: relative; z-index: 2; padding: 16px; display: flex; flex-direction: column; gap: 14px; }
.wx-main__top { display: flex; justify-content: space-between; align-items: center; }
.wx-main__city { display: flex; align-items: center; gap: 4px; background: rgba(255,255,255,0.15); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.2); border-radius: 20px; padding: 4px 12px; font-size: 13px; color: inherit; cursor: pointer; transition: background 0.15s; }
.wx-main__city:hover { background: rgba(255,255,255,0.25); }
.wx-main__actions { display: flex; gap: 4px; }
.wx-glass-icon { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.1); backdrop-filter: blur(8px); color: inherit; cursor: pointer; transition: background 0.15s; }
.wx-glass-icon:hover { background: rgba(255,255,255,0.2); }
.wx-glass-icon:disabled { opacity: 0.5; cursor: default; }
.wx-main__hero { text-align: center; padding: 8px 0; }
.wx-main__temp { font-size: 56px; font-weight: 200; line-height: 1; letter-spacing: -2px; text-shadow: 0 2px 8px rgba(0,0,0,0.15); }
.wx-main__desc { display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 14px; opacity: 0.9; margin-top: 4px; }
.wx-main__error { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px; gap: 10px; text-align: center; }

/* ── 指标卡 ── */
.wx-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.wx-metric-card { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 6px; border-radius: 12px; background: rgba(255,255,255,0.12); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.15); }
.wx-metric-card__val { font-size: 15px; font-weight: 600; }
.wx-metric-card__label { font-size: 10px; opacity: 0.7; }

/* ── 预报列表 ── */
.wx-forecast { display: flex; flex-direction: column; gap: 2px; background: rgba(255,255,255,0.08); backdrop-filter: blur(8px); border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); padding: 8px 12px; }
.wx-forecast__row { display: flex; align-items: center; padding: 5px 0; font-size: 13px; }
.wx-forecast__day { width: 42px; font-weight: 500; }
.wx-forecast__weekday { width: 32px; font-size: 11px; opacity: 0.6; }
.wx-forecast__icon { margin: 0 8px; }
.wx-forecast__range { margin-left: auto; display: flex; gap: 8px; }
.wx-forecast__hi { font-weight: 600; }
.wx-forecast__lo { opacity: 0.6; }

/* ── 城市选择视图 ── */
.wx-city-view { position: relative; z-index: 2; padding: 16px; display: flex; flex-direction: column; gap: 12px; min-height: 360px; }
.wx-city-view__header { display: flex; justify-content: space-between; align-items: center; }
.wx-city-view__title { font-size: 15px; font-weight: 600; }
.wx-glass-btn { display: flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.12); backdrop-filter: blur(8px); color: inherit; cursor: pointer; font-size: 12px; transition: background 0.15s; }
.wx-glass-btn:hover { background: rgba(255,255,255,0.22); }
.wx-city-view__search { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 10px; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); }
.wx-city-view__input { flex: 1; background: transparent; border: none; outline: none; color: inherit; font-size: 13px; }
.wx-city-view__input::placeholder { color: rgba(255,255,255,0.5); }
.wx-city-view__results { display: flex; flex-direction: column; gap: 2px; max-height: 160px; overflow-y: auto; }
.wx-city-view__hint { display: flex; align-items: center; gap: 6px; padding: 8px 0; justify-content: center; font-size: 12px; opacity: 0.7; }
.wx-city-btn { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 8px; border: none; background: rgba(255,255,255,0.08); color: inherit; cursor: pointer; font-size: 13px; text-align: left; transition: background 0.15s; }
.wx-city-btn:hover { background: rgba(255,255,255,0.18); }
.wx-city-btn--locate { background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.2); justify-content: center; font-weight: 500; }
.wx-city-btn--locate:disabled { opacity: 0.5; cursor: default; }
.wx-city-view__section { display: flex; flex-direction: column; gap: 6px; }
.wx-city-view__label { font-size: 11px; opacity: 0.6; font-weight: 500; }
.wx-city-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.wx-city-chip { padding: 4px 12px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.1); color: inherit; cursor: pointer; font-size: 12px; transition: background 0.15s, transform 0.1s; }
.wx-city-chip:hover { background: rgba(255,255,255,0.22); }
.wx-city-chip:active { transform: scale(0.95); }
`;
