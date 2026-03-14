/**
 * 天气插件样式 — Windows 11 Fluent Design
 *
 * 亚克力材质 + 柔和渐变 + 噪点纹理 + 精细动画
 * 通过 JS 注入 <head>（Popover portal 无法使用 scoped CSS）
 */
export const WX_STYLES = `
/* ── Popover 覆盖 ── */
.weather-popover-immersive.ant-popover .ant-popover-inner {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: 0 8px 40px rgba(0,0,0,0.32), 0 0 0 1px rgba(255,255,255,0.06) !important;
  border-radius: 16px !important;
  overflow: hidden !important;
}
.weather-popover-immersive.ant-popover .ant-popover-inner .ant-popover-inner-content {
  padding: 0 !important;
  width: 340px !important;
  max-width: 340px !important;
}
.weather-popover-immersive.ant-popover .ant-popover-arrow {
  display: none !important;
}

/* ── 视图切换过渡 ── */
.wx-view-enter-active, .wx-view-leave-active {
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.wx-view-enter-from { opacity: 0; transform: translateY(6px); }
.wx-view-leave-to { opacity: 0; transform: translateY(-6px); }

/* ── 内容渐入动画 ── */
.wx-fade-up {
  animation: wx-fadeInUp 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}
.wx-fade-up-1 { animation-delay: 0.05s; }
.wx-fade-up-2 { animation-delay: 0.1s; }
.wx-fade-up-3 { animation-delay: 0.15s; }
.wx-fade-up-4 { animation-delay: 0.2s; }
@keyframes wx-fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ══════════════════════════════════════
   天气背景渐变 (柔和低饱和度)
   ══════════════════════════════════════ */
.wx-bg--clear-day   { background: linear-gradient(175deg, #1a56db 0%, #2e7cf6 30%, #4a9af7 60%, #7bb8f9 100%); }
.wx-bg--clear-night { background: linear-gradient(175deg, #0a0f1f 0%, #101b3a 30%, #162550 65%, #1c3468 100%); }
.wx-bg--cloudy-day  { background: linear-gradient(175deg, #3d5a80 0%, #5a7da3 35%, #7d9bba 70%, #98b4cc 100%); }
.wx-bg--cloudy-night{ background: linear-gradient(175deg, #1a2744 0%, #253550 35%, #324563 70%, #3d5575 100%); }
.wx-bg--rain-day    { background: linear-gradient(175deg, #2c3e57 0%, #3e5571 35%, #506d8a 70%, #6685a3 100%); }
.wx-bg--rain-night  { background: linear-gradient(175deg, #0d1520 0%, #162030 35%, #1f2d42 70%, #283a54 100%); }
.wx-bg--snow-day    { background: linear-gradient(175deg, #6882a0 0%, #839ab5 30%, #9eb3cc 60%, #b8cce3 100%); }
.wx-bg--snow-night  { background: linear-gradient(175deg, #1e2b40 0%, #2a3a55 35%, #384b68 70%, #455c7a 100%); }
.wx-bg--thunder     { background: linear-gradient(175deg, #12102a 0%, #1a1640 30%, #231e55 60%, #2c2668 100%); }
.wx-bg--fog         { background: linear-gradient(175deg, #5c7a9a 0%, #7a96b3 35%, #96b0c9 70%, #b2c9de 100%); }

/* ══════════════════════════════════════
   亚克力材质
   ══════════════════════════════════════ */
.wx-acrylic {
  backdrop-filter: blur(16px) saturate(1.4);
  -webkit-backdrop-filter: blur(16px) saturate(1.4);
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.08);
}

/* 亚克力噪点纹理叠加 */
.wx-noise::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  opacity: 0.03;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 128px 128px;
}

/* ══════════════════════════════════════
   头部天气场景装饰
   ══════════════════════════════════════ */

/* 太阳光晕 */
.wx-sun-glow {
  position: absolute;
  top: -20px; right: -20px;
  width: 120px; height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(253,224,71,0.50) 0%, rgba(251,191,36,0.25) 40%, transparent 70%);
  box-shadow: 0 0 80px 30px rgba(253,224,71,0.18);
  animation: wx-glow-pulse 5s ease-in-out infinite;
}
@keyframes wx-glow-pulse {
  0%, 100% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
}

/* 月亮 */
.wx-moon-glow {
  position: absolute;
  top: -10px; right: -10px;
  width: 70px; height: 70px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(226,232,240,0.3) 0%, rgba(203,213,225,0.1) 50%, transparent 70%);
  box-shadow: 0 0 40px 10px rgba(226,232,240,0.08);
}
.wx-star-dot {
  position: absolute;
  width: 2px; height: 2px;
  background: rgba(255,255,255,0.6);
  border-radius: 50%;
  animation: wx-twinkle 3s ease-in-out infinite;
}
@keyframes wx-twinkle {
  0%, 100% { opacity: 0.2; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.3); }
}

/* 云朵光晕 */
.wx-cloud-glow {
  position: absolute;
  top: -15px; right: -5px;
  width: 120px; height: 80px;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgba(255,255,255,0.20) 0%, transparent 70%);
  filter: blur(8px);
  animation: wx-cloud-float 12s ease-in-out infinite;
}
@keyframes wx-cloud-float {
  0%, 100% { transform: translateX(0) translateY(0); }
  50% { transform: translateX(10px) translateY(-5px); }
}

/* 雨滴意象 */
.wx-rain-hint {
  position: absolute;
  top: 5px; right: 20px;
  width: 2px; height: 16px;
  background: linear-gradient(180deg, transparent, rgba(148,196,228,0.4));
  border-radius: 1px;
  animation: wx-rain-drift 1.5s ease-in-out infinite;
}
.wx-rain-hint:nth-child(2) { right: 35px; height: 12px; animation-delay: 0.3s; opacity: 0.6; }
.wx-rain-hint:nth-child(3) { right: 50px; height: 10px; animation-delay: 0.7s; opacity: 0.4; }
@keyframes wx-rain-drift {
  0% { opacity: 0; transform: translateY(-5px); }
  30% { opacity: 1; }
  100% { opacity: 0; transform: translateY(25px); }
}

/* 雪花意象 */
.wx-snow-hint {
  position: absolute;
  top: 8px;
  width: 4px; height: 4px;
  background: rgba(255,255,255,0.5);
  border-radius: 50%;
  animation: wx-snow-drift 3s ease-in-out infinite;
}
.wx-snow-hint:nth-child(1) { right: 20px; animation-delay: 0s; }
.wx-snow-hint:nth-child(2) { right: 40px; width: 3px; height: 3px; animation-delay: 0.8s; opacity: 0.6; }
.wx-snow-hint:nth-child(3) { right: 55px; width: 2px; height: 2px; animation-delay: 1.5s; opacity: 0.4; }
@keyframes wx-snow-drift {
  0% { opacity: 0; transform: translateY(-5px) rotate(0deg); }
  30% { opacity: 1; }
  100% { opacity: 0; transform: translateY(30px) rotate(180deg); }
}

/* 闪电意象 */
.wx-thunder-flash {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  animation: wx-flash 5s ease-in-out infinite;
}
@keyframes wx-flash {
  0%, 92%, 95%, 97%, 100% { background: transparent; }
  93% { background: rgba(255,255,255,0.08); }
  96% { background: rgba(255,255,255,0.04); }
}

/* 雾气意象 */
.wx-fog-layer {
  position: absolute;
  width: 150%; height: 30px;
  border-radius: 50%;
  filter: blur(15px);
  background: rgba(255,255,255,0.06);
}
.wx-fog-layer:nth-child(1) { top: 20%; left: -25%; animation: wx-fog-move 16s ease-in-out infinite; }
.wx-fog-layer:nth-child(2) { top: 50%; left: -15%; animation: wx-fog-move 12s ease-in-out infinite reverse; opacity: 0.5; }
@keyframes wx-fog-move {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(30px); }
}

/* ══════════════════════════════════════
   小时预报横向滚动
   ══════════════════════════════════════ */
.wx-hourly-scroll {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 10px 8px;
}
.wx-hourly-scroll::-webkit-scrollbar { display: none; }

.wx-hourly-item {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  transition: background 0.2s;
  min-width: 52px;
}
.wx-hourly-item--current {
  background: rgba(255,255,255,0.1);
}

/* ══════════════════════════════════════
   面板滚动条
   ══════════════════════════════════════ */
.wx-panel-scroll {
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.15) transparent;
}
.wx-panel-scroll::-webkit-scrollbar { width: 3px; }
.wx-panel-scroll::-webkit-scrollbar-track { background: transparent; }
.wx-panel-scroll::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.15);
  border-radius: 3px;
}

/* ══════════════════════════════════════
   骨架屏脉冲
   ══════════════════════════════════════ */
.wx-skeleton {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.1) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 200% 100%;
  animation: wx-shimmer 1.8s ease-in-out infinite;
  border-radius: 8px;
}
@keyframes wx-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ══════════════════════════════════════
   大天气图标
   ══════════════════════════════════════ */
.wx-hero-icon {
  width: 56px; height: 56px;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,0.15));
  opacity: 0.9;
}

/* ══════════════════════════════════════
   指标卡片色彩点缀
   ══════════════════════════════════════ */
.wx-metric-feels,
.wx-metric-humidity,
.wx-metric-wind,
.wx-metric-uv,
.wx-metric-aqi,
.wx-metric-sun { position: relative; overflow: hidden; }

.wx-metric-feels::before,
.wx-metric-humidity::before,
.wx-metric-wind::before,
.wx-metric-uv::before,
.wx-metric-aqi::before,
.wx-metric-sun::before {
  content: '';
  position: absolute;
  top: 0; left: 50%;
  transform: translateX(-50%);
  width: 24px; height: 2px;
  border-radius: 0 0 2px 2px;
}
.wx-metric-feels::before    { background: linear-gradient(90deg, #f97316, #fb923c); }
.wx-metric-humidity::before { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.wx-metric-wind::before     { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
.wx-metric-uv::before       { background: linear-gradient(90deg, #eab308, #fbbf24); }
.wx-metric-aqi::before      { background: linear-gradient(90deg, #22c55e, #4ade80); }
.wx-metric-sun::before      { background: linear-gradient(90deg, #f59e0b, #fbbf24); }

/* ══════════════════════════════════════
   面板内发光
   ══════════════════════════════════════ */
.wx-panel-inner-glow {
  position: absolute;
  top: 0; left: 10%; right: 10%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  pointer-events: none;
  z-index: 3;
}

/* ══════════════════════════════════════
   温度条渐变
   ══════════════════════════════════════ */
.wx-temp-bar-track {
  position: relative;
  height: 5px;
  border-radius: 9999px;
  background: rgba(255,255,255,0.12);
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.15);
}
.wx-temp-bar-fill {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 9999px;
  box-shadow: 0 0 6px rgba(255,255,255,0.15);
}
`;
