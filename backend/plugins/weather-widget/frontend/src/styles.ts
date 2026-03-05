/**
 * 天气插件非 Tailwind 样式（字符串形式）
 *
 * 布局/排版已迁移到 Tailwind（WeatherHeaderWidget.vue 模板中）。
 * 仅保留无法用 Tailwind 实现的样式：Popover portal 覆盖、天气渐变背景、粒子动画/伪元素。
 * 通过 setup() 用 JS 注入到 <head>，以 .wx- 前缀避免冲突。
 */
export const WX_STYLES = `
/* ── Popover 覆盖（portal 渲染，无法用 Tailwind） ── */
.weather-popover-immersive.ant-popover .ant-popover-inner {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: 0 8px 32px rgba(0,0,0,0.28) !important;
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
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.wx-view-enter-from {
  opacity: 0; transform: translateY(8px);
}
.wx-view-leave-to {
  opacity: 0; transform: translateY(-8px);
}

/* ── 天气背景渐变 ── */
.wx-bg--clear-day { background: linear-gradient(170deg, #1565c0 0%, #1e88e5 40%, #42a5f5 100%); }
.wx-bg--clear-night { background: linear-gradient(170deg, #070e1a 0%, #0d1b2a 40%, #162d50 100%); }
.wx-bg--cloudy-day { background: linear-gradient(170deg, #546e7a 0%, #607d8b 50%, #78909c 100%); }
.wx-bg--cloudy-night { background: linear-gradient(170deg, #1a2530 0%, #263238 50%, #37474f 100%); }
.wx-bg--rain-day { background: linear-gradient(170deg, #37474f 0%, #455a64 50%, #546e7a 100%); }
.wx-bg--rain-night { background: linear-gradient(170deg, #0d1117 0%, #161b22 50%, #1c2128 100%); }
.wx-bg--snow-day { background: linear-gradient(170deg, #78909c 0%, #90a4ae 50%, #b0bec5 100%); }
.wx-bg--snow-night { background: linear-gradient(170deg, #263238 0%, #37474f 50%, #455a64 100%); }
.wx-bg--thunder { background: linear-gradient(170deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%); }
.wx-bg--fog { background: linear-gradient(170deg, #78909c 0%, #90a4ae 50%, #b0bec5 100%); }

/* ══════════════════════════════════════════════════
   天气场景动画
   ══════════════════════════════════════════════════ */

/* ── 太阳（晴天白天）── */
.wx-sun {
  position: absolute; top: 8%; right: 10%;
  width: 70px; height: 70px; border-radius: 50%;
  background: radial-gradient(circle, rgba(255,236,179,0.9) 0%, rgba(255,193,7,0.5) 40%, transparent 70%);
  box-shadow: 0 0 40px 15px rgba(255,193,7,0.25), 0 0 80px 30px rgba(255,193,7,0.1);
  animation: wx-sun-pulse 4s ease-in-out infinite;
}
.wx-sun-ray {
  position: absolute; top: 8%; right: 10%;
  width: 70px; height: 70px;
  animation: wx-sun-rotate 20s linear infinite;
}
.wx-sun-ray::before, .wx-sun-ray::after {
  content: ''; position: absolute;
  top: 50%; left: 50%;
  width: 120px; height: 2px;
  background: linear-gradient(90deg, transparent, rgba(255,236,179,0.3), transparent);
  transform-origin: center;
}
.wx-sun-ray::before { transform: translate(-50%, -50%) rotate(0deg); }
.wx-sun-ray::after { transform: translate(-50%, -50%) rotate(60deg); }
@keyframes wx-sun-pulse { 0%, 100% { transform: scale(1); opacity: 0.9; } 50% { transform: scale(1.08); opacity: 1; } }
@keyframes wx-sun-rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ── 月亮 + 星星（晴天夜晚）── */
.wx-moon {
  position: absolute; top: 10%; right: 12%;
  width: 50px; height: 50px; border-radius: 50%;
  background: #e8e8d0;
  box-shadow: 0 0 20px 5px rgba(232,232,208,0.2), inset -8px 2px 0 0 rgba(0,0,0,0.06);
}
.wx-star {
  position: absolute; width: 2px; height: 2px;
  background: rgba(255,255,255,0.8); border-radius: 50%;
  animation: wx-twinkle 3s ease-in-out infinite;
}
@keyframes wx-twinkle { 0%, 100% { opacity: 0.2; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }

/* ── 云朵（多云）── */
.wx-cloud {
  position: absolute; border-radius: 50px;
  background: rgba(255,255,255,0.18);
  filter: blur(2px);
}
.wx-cloud::before, .wx-cloud::after {
  content: ''; position: absolute;
  background: inherit; border-radius: 50%;
}
.wx-cloud--lg { width: 100px; height: 36px; top: 15%; right: -10px; animation: wx-drift 16s ease-in-out infinite; }
.wx-cloud--lg::before { width: 44px; height: 44px; top: -24px; left: 18px; }
.wx-cloud--lg::after { width: 32px; height: 32px; top: -16px; left: 50px; }
.wx-cloud--md { width: 70px; height: 26px; top: 30%; left: 5%; animation: wx-drift 20s ease-in-out infinite reverse; opacity: 0.7; }
.wx-cloud--md::before { width: 30px; height: 30px; top: -18px; left: 12px; }
.wx-cloud--md::after { width: 22px; height: 22px; top: -12px; left: 34px; }
.wx-cloud--sm { width: 50px; height: 20px; top: 22%; left: 40%; animation: wx-drift 14s ease-in-out infinite; opacity: 0.5; }
.wx-cloud--sm::before { width: 22px; height: 22px; top: -14px; left: 8px; }
.wx-cloud--sm::after { width: 18px; height: 18px; top: -10px; left: 24px; }
@keyframes wx-drift { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(30px); } }

/* ── 雨滴 ── */
.wx-rain {
  position: absolute; width: 1.5px; height: 18px;
  background: linear-gradient(180deg, transparent, rgba(174,213,240,0.6));
  top: -20px; left: calc(var(--i) * 7.5%);
  animation: wx-rain-fall 0.7s linear infinite;
  animation-delay: calc(var(--i) * 0.06s); opacity: 0;
}
@keyframes wx-rain-fall { 0% { opacity: 0; transform: translateY(0); } 15% { opacity: 0.7; } 100% { opacity: 0; transform: translateY(500px); } }

/* ── 雨天云朵（深色压顶） ── */
.wx-rain-cloud {
  position: absolute; border-radius: 50px;
  background: rgba(0,0,0,0.15);
  filter: blur(4px);
}
.wx-rain-cloud::before, .wx-rain-cloud::after {
  content: ''; position: absolute;
  background: inherit; border-radius: 50%;
}
.wx-rain-cloud--1 { width: 130px; height: 40px; top: -8px; left: 10%; }
.wx-rain-cloud--1::before { width: 50px; height: 50px; top: -28px; left: 25px; }
.wx-rain-cloud--1::after { width: 38px; height: 38px; top: -20px; left: 65px; }
.wx-rain-cloud--2 { width: 100px; height: 32px; top: 0; right: 5%; opacity: 0.7; }
.wx-rain-cloud--2::before { width: 36px; height: 36px; top: -22px; left: 20px; }
.wx-rain-cloud--2::after { width: 28px; height: 28px; top: -16px; left: 50px; }

/* ── 雪花 ── */
.wx-snow {
  position: absolute; width: 5px; height: 5px;
  background: rgba(255,255,255,0.85); border-radius: 50%;
  top: -10px; left: calc(var(--i) * 9%);
  animation: wx-snow-fall 3.5s ease-in-out infinite;
  animation-delay: calc(var(--i) * 0.25s); opacity: 0;
}
@keyframes wx-snow-fall { 0% { opacity: 0; transform: translateY(0) translateX(0) rotate(0deg); } 15% { opacity: 0.9; } 100% { opacity: 0; transform: translateY(500px) translateX(20px) rotate(360deg); } }

/* ── 雪天云朵（浅色柔和） ── */
.wx-snow-cloud {
  position: absolute; border-radius: 50px;
  background: rgba(255,255,255,0.12);
  filter: blur(3px);
}
.wx-snow-cloud::before, .wx-snow-cloud::after {
  content: ''; position: absolute;
  background: inherit; border-radius: 50%;
}
.wx-snow-cloud--1 { width: 110px; height: 36px; top: 2%; left: 15%; }
.wx-snow-cloud--1::before { width: 42px; height: 42px; top: -24px; left: 20px; }
.wx-snow-cloud--1::after { width: 30px; height: 30px; top: -16px; left: 55px; }

/* ── 闪电（雷暴） ── */
.wx-lightning {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255,255,255,0);
  animation: wx-flash 4s ease-in-out infinite;
}
@keyframes wx-flash {
  0%, 100% { background: rgba(255,255,255,0); }
  92% { background: rgba(255,255,255,0); }
  93% { background: rgba(255,255,255,0.15); }
  94% { background: rgba(255,255,255,0); }
  96% { background: rgba(255,255,255,0.08); }
  97% { background: rgba(255,255,255,0); }
}
.wx-bolt {
  position: absolute; top: 12%; left: 55%;
  width: 3px; height: 0;
  background: rgba(255,255,200,0.9);
  filter: blur(1px);
  box-shadow: 0 0 8px 2px rgba(255,255,200,0.4);
  animation: wx-bolt-strike 4s ease-in-out infinite;
  transform-origin: top center;
}
.wx-bolt::after {
  content: ''; position: absolute;
  top: 100%; left: -4px;
  width: 3px; height: 0;
  background: inherit; filter: inherit;
  box-shadow: inherit;
  transform: rotate(25deg); transform-origin: top center;
  animation: wx-bolt-branch 4s ease-in-out infinite;
}
@keyframes wx-bolt-strike {
  0%, 91%, 98%, 100% { height: 0; opacity: 0; }
  93% { height: 50px; opacity: 1; }
  94% { height: 50px; opacity: 0; }
  96% { height: 40px; opacity: 0.7; }
  97% { height: 40px; opacity: 0; }
}
@keyframes wx-bolt-branch {
  0%, 91%, 98%, 100% { height: 0; opacity: 0; }
  93% { height: 25px; opacity: 0.8; }
  94% { height: 25px; opacity: 0; }
  96% { height: 20px; opacity: 0.5; }
  97% { height: 20px; opacity: 0; }
}

/* ── 雾气 ── */
.wx-fog {
  position: absolute; width: 200%; height: 50px; border-radius: 50%;
  filter: blur(25px);
}
.wx-fog--1 { top: 25%; left: -50%; background: rgba(255,255,255,0.1); animation: wx-fog-drift 18s ease-in-out infinite; }
.wx-fog--2 { top: 50%; left: -30%; background: rgba(255,255,255,0.07); animation: wx-fog-drift 14s ease-in-out infinite reverse; }
.wx-fog--3 { top: 70%; left: -40%; background: rgba(255,255,255,0.05); animation: wx-fog-drift 22s ease-in-out infinite; }
@keyframes wx-fog-drift { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(50px); } }
`;

