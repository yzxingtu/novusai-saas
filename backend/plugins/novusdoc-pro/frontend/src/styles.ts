/**
 * Novusdoc Pro 插件样式
 *
 * 通过 setup() JS 注入到 <head>，避免 scoped CSS 在 portal 中失效。
 * 以 .ndp- 前缀避免全局冲突。
 */
export const NDP_STYLES = `
/* NovusDoc Pro collaboration styles (.ndp- prefix) */

/* Collaboration cursor colors (8-color rotation) */
.ndp-cursor-1 { --cursor-color: #F87171; }
.ndp-cursor-2 { --cursor-color: #FB923C; }
.ndp-cursor-3 { --cursor-color: #FBBF24; }
.ndp-cursor-4 { --cursor-color: #34D399; }
.ndp-cursor-5 { --cursor-color: #60A5FA; }
.ndp-cursor-6 { --cursor-color: #A78BFA; }
.ndp-cursor-7 { --cursor-color: #F472B6; }
.ndp-cursor-8 { --cursor-color: #2DD4BF; }

/* Remote cursor indicator */
.ndp-collab-cursor {
  position: relative;
  border-left: 2px solid var(--cursor-color, #60A5FA);
  margin-left: -1px;
}
.ndp-collab-cursor-label {
  position: absolute;
  top: -1.4em;
  left: -1px;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px 4px 4px 0;
  background: var(--cursor-color, #60A5FA);
  color: white;
  white-space: nowrap;
  pointer-events: none;
}

/* Online users avatars */
.ndp-collab-avatars {
  display: flex;
  align-items: center;
  gap: 0;
}
.ndp-collab-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid hsl(var(--background));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
}

/* Comment highlight in editor */
.ndp-comment-mark {
  background: rgba(251, 191, 36, 0.2);
  border-bottom: 2px solid #FBBF24;
}
.ndp-comment-mark.ndp-resolved {
  background: rgba(156, 163, 175, 0.1);
  border-bottom-color: #9CA3AF;
}
`;
