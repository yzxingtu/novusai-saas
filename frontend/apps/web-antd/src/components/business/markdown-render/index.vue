<script setup lang="ts">
/**
 * Markdown Render Component
 * Markdown 渲染组件
 *
 * Based on markdown-it + highlight.js, supports code highlighting, copy, and streaming render.
 * 基于 markdown-it + highlight.js，支持代码高亮、复制、流式渲染。
 * Reusable business component for chat UI, version details, etc.
 * 作为通用业务组件供对话界面、版本详情等场景复用。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { message } from 'ant-design-vue';
import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import css from 'highlight.js/lib/languages/css';
import go from 'highlight.js/lib/languages/go';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import markdown from 'highlight.js/lib/languages/markdown';
import python from 'highlight.js/lib/languages/python';
import rust from 'highlight.js/lib/languages/rust';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';

import { $t } from '#/locales';

defineOptions({ name: 'MarkdownRender' });

const props = withDefaults(
  defineProps<{
    /** Markdown text content / Markdown 文本内容 */
    content: string;
    /** Streaming mode (receiving data, skip some post-processing) / 流式模式 */
    streaming?: boolean;
  }>(),
  {
    streaming: false,
  },
);
// Register common languages / 注册常用语言
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('js', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('ts', typescript);
hljs.registerLanguage('python', python);
hljs.registerLanguage('py', python);
hljs.registerLanguage('java', java);
hljs.registerLanguage('go', go);
hljs.registerLanguage('rust', rust);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('sh', bash);
hljs.registerLanguage('shell', bash);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('json', json);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('yml', yaml);
hljs.registerLanguage('css', css);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('md', markdown);

// Initialize markdown-it / 初始化 markdown-it
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str: string, lang: string): string {
    const langLabel = lang || 'text';
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(str, { language: lang }).value;
        return buildCodeBlock(highlighted, langLabel);
      } catch {
        // fallback / 高亮失败则走下方自动检测
      }
    }
    // Auto-detect / 自动检测
    try {
      const result = hljs.highlightAuto(str);
      return buildCodeBlock(result.value, result.language || langLabel);
    } catch {
      return buildCodeBlock(md.utils.escapeHtml(str), langLabel);
    }
  },
});

// Open links in new window / 链接在新窗口打开
const defaultRender =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options);
  };
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  tokens[idx]?.attrSet('target', '_blank');
  tokens[idx]?.attrSet('rel', 'noopener noreferrer');
  return defaultRender(tokens, idx, options, env, self);
};

/** Build code block HTML with language label and copy button / 构建带语言标签和复制按钮的代码块 HTML */
function buildCodeBlock(highlighted: string, lang: string): string {
  const id = `code-${Math.random().toString(36).slice(2, 10)}`;
  return (
    `<div class="md-code-block">` +
    `<div class="md-code-header">` +
    `<span class="md-code-lang">${lang}</span>` +
    `<button class="md-code-copy" data-code-id="${id}">` +
    `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>` +
    `</button>` +
    `</div>` +
    `<pre class="hljs"><code id="${id}">${highlighted}</code></pre>` +
    `</div>`
  );
}

const containerRef = ref<HTMLElement>();

function handleCopyClick(e: Event) {
  const btn = (e.target as HTMLElement).closest<HTMLElement>('.md-code-copy');
  if (!btn) return;
  const codeId = btn.dataset.codeId;
  if (!codeId) return;
  const el = document.querySelector<HTMLElement>(`#${CSS.escape(codeId)}`);
  if (el) {
    navigator.clipboard
      .writeText(el.textContent || '')
      .then(() => message.success($t('common.globalAiChat.copySuccess')))
      .catch(() => message.error($t('common.requestFailed')));
  }
}

onMounted(() => {
  containerRef.value?.addEventListener('click', handleCopyClick);
});

onBeforeUnmount(() => {
  containerRef.value?.removeEventListener('click', handleCopyClick);
});

const renderedHtml = computed(() => {
  if (!props.content) return '';
  try {
    const raw = md.render(props.content);
    return DOMPurify.sanitize(raw);
  } catch {
    return DOMPurify.sanitize(`<pre style="white-space:pre-wrap;word-break:break-word">${md.utils.escapeHtml(props.content)}</pre>`);
  }
});
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div ref="containerRef" class="markdown-render" v-html="renderedHtml"></div>
</template>

<style>
.markdown-render {
  font-size: 14px;
  line-height: 1.7;
  word-break: normal;
  overflow-wrap: anywhere;
}

.markdown-render p {
  margin: 0.4em 0;
}

.markdown-render ul,
.markdown-render ol {
  padding-left: 1.5em;
  margin: 0.4em 0;
}

.markdown-render blockquote {
  padding-left: 0.8em;
  margin: 0.4em 0;
  color: hsl(var(--muted-foreground));
  border-left: 3px solid hsl(var(--primary));
}

.markdown-render table {
  width: 100%;
  margin: 0.5em 0;
  border-collapse: collapse;
}

.markdown-render th,
.markdown-render td {
  padding: 6px 12px;
  text-align: left;
  border: 1px solid hsl(var(--border));
}

.markdown-render th {
  font-weight: 600;
  background: hsl(var(--accent));
}

.markdown-render a {
  color: hsl(var(--primary));
  text-decoration: underline;
}

/* Code blocks / 代码块 */
.md-code-block {
  margin: 0.5em 0;
  overflow: hidden;
  border: 1px solid hsl(var(--border));
  border-radius: 8px;
}

.md-code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  font-size: 12px;
  background: hsl(var(--accent));
}

.md-code-lang {
  font-family: monospace;
  color: hsl(var(--muted-foreground));
}

.md-code-copy {
  display: inline-flex;
  align-items: center;
  padding: 2px;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 4px;
  transition: color 0.2s;
}

.md-code-copy:hover {
  color: hsl(var(--foreground));
}

.md-code-block pre.hljs {
  padding: 12px 16px;
  margin: 0;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
  background: hsl(var(--accent) / 30%);
}

.md-code-block pre.hljs code {
  font-family: 'Fira Code', Consolas, Monaco, monospace;
}

/* Inline code / 行内代码 */
.markdown-render code:not(.hljs code) {
  padding: 1px 5px;
  font-family: 'Fira Code', Consolas, Monaco, monospace;
  font-size: 0.9em;
  background: hsl(var(--accent));
  border-radius: 4px;
}

/* highlight.js base colors / highlight.js 基础色 */
.hljs-keyword {
  color: #c678dd;
}

.hljs-string {
  color: #98c379;
}

.hljs-number {
  color: #d19a66;
}

.hljs-comment {
  font-style: italic;
  color: #5c6370;
}

.hljs-function {
  color: #61afef;
}

.hljs-title {
  color: #e5c07b;
}

/* stylelint-disable-next-line selector-class-pattern */
.hljs-built_in {
  color: #e06c75;
}

.hljs-attr {
  color: #d19a66;
}

.hljs-params {
  color: #abb2bf;
}

.hljs-literal {
  color: #56b6c2;
}

.hljs-type {
  color: #e5c07b;
}
</style>
