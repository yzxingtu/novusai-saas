<script setup lang="ts">
/**
 * Markdown 渲染组件
 *
 * 基于 markdown-it + highlight.js，支持代码高亮、复制、流式渲染。
 * 作为通用业务组件供对话界面、版本详情等场景复用。
 */
defineOptions({ name: 'MarkdownRender' });

import { computed, onMounted, onBeforeUnmount, ref } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';

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
import MarkdownIt from 'markdown-it';

// 注册常用语言
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

const props = withDefaults(
  defineProps<{
    /** Markdown 文本内容 */
    content: string;
    /** 流式模式（正在接收中，跳过某些后处理） */
    streaming?: boolean;
  }>(),
  {
    streaming: false,
  },
);

// 初始化 markdown-it
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
        // fallback
      }
    }
    // 自动检测
    try {
      const result = hljs.highlightAuto(str);
      return buildCodeBlock(result.value, result.language || langLabel);
    } catch {
      return buildCodeBlock(md.utils.escapeHtml(str), langLabel);
    }
  },
});

// 链接在新窗口打开
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

/** 构建带语言标签和复制按钮的代码块 HTML */
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
  const el = document.getElementById(codeId);
  if (el) {
    navigator.clipboard
      .writeText(el.textContent || '')
      .then(() => message.success($t('common.copied')))
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
  return md.render(props.content);
});

</script>

<template>
  <div
    ref="containerRef"
    class="markdown-render"
    v-html="renderedHtml"
  />
</template>

<style>
.markdown-render {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
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
  border-left: 3px solid hsl(var(--primary));
  padding-left: 0.8em;
  margin: 0.4em 0;
  color: hsl(var(--muted-foreground));
}

.markdown-render table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
}

.markdown-render th,
.markdown-render td {
  border: 1px solid hsl(var(--border));
  padding: 6px 12px;
  text-align: left;
}

.markdown-render th {
  background: hsl(var(--accent));
  font-weight: 600;
}

.markdown-render a {
  color: hsl(var(--primary));
  text-decoration: underline;
}

/* 代码块 */
.md-code-block {
  border-radius: 8px;
  overflow: hidden;
  margin: 0.5em 0;
  border: 1px solid hsl(var(--border));
}

.md-code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: hsl(var(--accent));
  font-size: 12px;
}

.md-code-lang {
  color: hsl(var(--muted-foreground));
  font-family: monospace;
}

.md-code-copy {
  display: inline-flex;
  align-items: center;
  border: none;
  background: transparent;
  cursor: pointer;
  color: hsl(var(--muted-foreground));
  padding: 2px;
  border-radius: 4px;
  transition: color 0.2s;
}

.md-code-copy:hover {
  color: hsl(var(--foreground));
}

.md-code-block pre.hljs {
  margin: 0;
  padding: 12px 16px;
  overflow-x: auto;
  background: hsl(var(--accent) / 0.3);
  font-size: 13px;
  line-height: 1.5;
}

.md-code-block pre.hljs code {
  font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
}

/* 行内代码 */
.markdown-render code:not(.hljs code) {
  background: hsl(var(--accent));
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
}

/* highlight.js 基础色 */
.hljs-keyword { color: #c678dd; }
.hljs-string { color: #98c379; }
.hljs-number { color: #d19a66; }
.hljs-comment { color: #5c6370; font-style: italic; }
.hljs-function { color: #61afef; }
.hljs-title { color: #e5c07b; }
.hljs-built_in { color: #e06c75; }
.hljs-attr { color: #d19a66; }
.hljs-params { color: #abb2bf; }
.hljs-literal { color: #56b6c2; }
.hljs-type { color: #e5c07b; }
</style>
