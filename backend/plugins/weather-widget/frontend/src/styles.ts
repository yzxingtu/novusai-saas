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

/* ── 天气背景渐变（动态 :class 切换） ── */
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

/* ── 粒子动画（keyframes + calc(var(--i)) + 伪元素） ── */
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
`;
