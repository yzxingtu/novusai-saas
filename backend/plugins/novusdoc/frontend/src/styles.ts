/**
 * NovusDoc 插件样式
 *
 * 通过 setup() JS 注入到 <head>，避免 scoped CSS 在 portal 中失效。
 * 以 .nd- 前缀避免全局冲突。
 */
export const ND_STYLES = `
/* ── NovusDoc plugin styles ── */
/* Design Tokens (CSS variables scoped to NovusDoc) */
:root {
  --nd-radius-sm: 6px;
  --nd-radius-md: 10px;
  --nd-radius-lg: 14px;
  --nd-shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --nd-shadow-md: 0 4px 16px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.04);
  --nd-shadow-lg: 0 8px 30px rgba(0,0,0,0.1), 0 2px 6px rgba(0,0,0,0.04);
  --nd-transition-fast: 120ms ease;
  --nd-transition-normal: 200ms ease;
  --nd-transition-slow: 300ms ease;
  --nd-content-width: 760px;
  --nd-sidebar-width: 240px;
}

/* Document list page layout */
.nd-doc-list-page {
  display: flex;
  height: 100%;
  min-height: 0;
}

/* Sidebar */
.nd-sidebar {
  width: var(--nd-sidebar-width);
  min-width: var(--nd-sidebar-width);
  border-right: 1px solid hsl(var(--border));
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  background: hsl(var(--background));
}
.nd-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 16px 12px;
}
.nd-folder-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.nd-folder-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  border-radius: var(--nd-radius-sm);
  margin: 2px 0;
  transition: all var(--nd-transition-fast);
  color: hsl(var(--foreground));
}
.nd-folder-item:hover { background: hsl(var(--accent)); }
.nd-folder-active {
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  font-weight: 600;
}

/* Main content area */
.nd-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px 28px;
  min-width: 0;
  overflow-y: auto;
  background: hsl(var(--background));
}
.nd-toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 12px;
}
.nd-empty {
  display: flex;
  justify-content: center;
  padding: 80px 0;
  opacity: 0.8;
}

/* Document grid */
.nd-doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.nd-doc-card {
  border: 1px solid hsl(var(--border));
  border-radius: var(--nd-radius-md);
  padding: 18px 20px;
  cursor: pointer;
  position: relative;
  transition: all var(--nd-transition-normal);
  background: hsl(var(--card));
}
.nd-doc-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--nd-shadow-md);
  border-color: hsl(var(--primary) / 0.2);
}
.nd-doc-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.nd-doc-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: hsl(var(--foreground));
}
.nd-doc-card-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid hsl(var(--border) / 0.5);
}
.nd-doc-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.nd-doc-card-star { position: absolute; top: 10px; right: 10px; }

/* ── Editor page ── */
.nd-editor-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: hsl(var(--background));
}
.nd-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid hsl(var(--border));
  min-height: 48px;
  background: hsl(var(--background) / 0.85);
  backdrop-filter: blur(12px);
  z-index: 10;
}
.nd-title-input {
  border: none;
  outline: none;
  font-size: 15px;
  font-weight: 600;
  background: transparent;
  color: hsl(var(--foreground));
  width: 300px;
  padding: 4px 10px;
  border-radius: var(--nd-radius-sm);
  transition: background var(--nd-transition-fast);
}
.nd-title-input:focus { background: hsl(var(--accent)); }
.nd-title-input::placeholder { color: hsl(var(--muted-foreground)); }

/* Toolbar */
.nd-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 16px;
  border-bottom: 1px solid hsl(var(--border));
  flex-wrap: wrap;
  background: hsl(var(--background));
}
.nd-toolbar-sep {
  width: 1px;
  height: 20px;
  background: hsl(var(--border));
  margin: 0 4px;
  flex-shrink: 0;
}
.nd-toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--nd-radius-sm);
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all var(--nd-transition-fast);
}
.nd-toolbar-btn:hover {
  background: hsl(var(--accent));
  color: hsl(var(--foreground));
}
.nd-toolbar-btn.nd-active {
  background: hsl(var(--primary) / 0.12);
  color: hsl(var(--primary));
}
.nd-toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Editor content area */
.nd-editor-content {
  max-width: var(--nd-content-width);
  margin: 0 auto;
  padding: 36px 64px;
  width: 100%;
  flex: 1;
}
.nd-editor-wrapper { min-height: 400px; }

/* Tiptap ProseMirror overrides */
.nd-editor-wrapper .ProseMirror { outline: none; min-height: 300px; }
.nd-editor-wrapper .ProseMirror p.is-editor-empty:first-child::before {
  color: hsl(var(--muted-foreground));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
.nd-editor-wrapper .ProseMirror img.nd-image { max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0; }
.nd-editor-wrapper .ProseMirror a.nd-link { color: hsl(var(--primary)); text-decoration: underline; }
.nd-editor-wrapper .ProseMirror pre { background: hsl(var(--accent)); border-radius: 8px; padding: 12px 16px; overflow-x: auto; }
.nd-editor-wrapper .ProseMirror blockquote { border-left: 3px solid hsl(var(--primary)); padding-left: 16px; margin-left: 0; color: hsl(var(--muted-foreground)); }
.nd-editor-wrapper .ProseMirror table { border-collapse: collapse; width: 100%; }
.nd-editor-wrapper .ProseMirror td, .nd-editor-wrapper .ProseMirror th { border: 1px solid hsl(var(--border)); padding: 8px 12px; text-align: left; }
.nd-editor-wrapper .ProseMirror th { background: hsl(var(--accent)); font-weight: 600; }
.nd-editor-wrapper .ProseMirror ul[data-type="taskList"] li { display: flex; align-items: flex-start; gap: 8px; }
.nd-editor-wrapper .ProseMirror ul[data-type="taskList"] li > label { margin-top: 3px; }

/* ── BubbleMenu: 覆盖 Tippy.js 默认黑色背景（portal 挂在 body 上，scoped CSS 无法覆盖） ── */
.tippy-box[data-theme="none"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
}
.tippy-box[data-theme="none"] .tippy-content {
  padding: 0 !important;
}
.tippy-box[data-theme="none"] .tippy-arrow { display: none !important; }

/* ── AI Result Panel (fixed below editor content) ── */
.nd-ai-result-panel {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 16px;
  background: hsl(var(--background));
  border-top: 1px solid hsl(var(--border));
  z-index: 10;
}

.nd-ai-result-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.nd-ai-result-dots {
  display: flex;
  gap: 3px;
}

.nd-ai-rdot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: hsl(var(--primary));
  animation: nd-rdot-anim 1.4s infinite ease-in-out;
}
.nd-ai-rdot:nth-child(2) { animation-delay: 0.2s; }
.nd-ai-rdot:nth-child(3) { animation-delay: 0.4s; }

@keyframes nd-rdot-anim {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.nd-ai-result-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nd-ai-result-text {
  font-size: 13px;
  line-height: 1.6;
  color: hsl(var(--foreground));
  max-height: 150px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 8px 12px;
  border-radius: 8px;
  background: hsl(var(--muted));
}

.nd-ai-result-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.nd-ai-result-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  color: hsl(var(--destructive));
}

/* ══════════════════════════════════════════════════════════
   F14: Responsive Breakpoints
   - Desktop: >= 1024px (default)
   - Tablet:  768px – 1023px
   - Mobile:  < 768px
   ══════════════════════════════════════════════════════════ */

/* ── Tablet (768px – 1023px) ── */
@media (max-width: 1023px) {
  .nd-sidebar {
    width: 200px;
    min-width: 200px;
  }
  .nd-doc-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }
  .nd-editor-content {
    padding: 24px 32px;
  }
  .nd-toolbar {
    padding: 4px 12px;
    overflow-x: auto;
    flex-wrap: nowrap;
  }
  .nd-ai-sidebar {
    width: 280px;
    min-width: 240px;
  }
}

/* ── Mobile (< 768px) ── */
@media (max-width: 767px) {
  /* List page: stack sidebar above main */
  .nd-doc-list-page {
    flex-direction: column;
  }
  .nd-sidebar {
    width: 100%;
    min-width: unset;
    max-height: 140px;
    border-right: none;
    border-bottom: 1px solid hsl(var(--border));
    padding: 8px 0;
  }
  .nd-folder-list {
    display: flex;
    overflow-x: auto;
    padding: 0 8px;
    gap: 4px;
  }
  .nd-folder-item {
    white-space: nowrap;
    flex-shrink: 0;
    padding: 6px 12px;
    margin: 0;
  }
  .nd-main {
    padding: 12px 16px;
  }
  .nd-toolbar-row {
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
  }
  .nd-doc-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .nd-doc-card {
    padding: 14px 16px;
  }

  /* Editor page */
  .nd-editor-header {
    padding: 6px 12px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .nd-title-input {
    width: 100%;
    min-width: 0;
    font-size: 14px;
  }
  .nd-toolbar {
    padding: 4px 8px;
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
  }
  .nd-toolbar-btn {
    width: 36px;
    height: 36px;
    min-width: 36px;
  }
  .nd-editor-content {
    padding: 16px;
  }

  /* AI sidebar becomes full-width overlay on mobile */
  .nd-ai-sidebar {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    max-width: 100%;
    z-index: 100;
    box-shadow: var(--nd-shadow-lg, 0 8px 30px rgba(0,0,0,0.1));
  }
}

/* ── Collaboration avatars ── */
.nd-collab-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  border: 2px solid hsl(var(--background));
  cursor: default;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

/* ── F15: A11y focus-visible styles ── */
.nd-toolbar-btn:focus-visible,
.nd-folder-item:focus-visible,
.nd-doc-card:focus-visible {
  outline: 2px solid hsl(var(--primary));
  outline-offset: 2px;
  border-radius: var(--nd-radius-sm, 6px);
}

/* Touch-friendly: larger tap targets on touch devices */
@media (pointer: coarse) {
  .nd-toolbar-btn {
    width: 36px;
    height: 36px;
    min-width: 36px;
  }
  .nd-ai-bm-icon {
    width: 34px;
    height: 34px;
  }
  .nd-folder-item {
    padding: 10px 14px;
  }
  .nd-doc-card {
    padding: 16px 18px;
  }
}
`;
