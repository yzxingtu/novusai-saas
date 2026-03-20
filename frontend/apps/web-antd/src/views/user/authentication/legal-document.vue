<script lang="ts" setup>
/**
 * Tenant legal document (privacy / terms) — full document template inside auth layout.
 * 企业法律文档：在认证布局的「文档模式」下以正文模板展示
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Button, Spin } from 'ant-design-vue';
import DOMPurify from 'dompurify';

import { getTenantLegalDocumentApi } from '#/api/public/config';
import { $t } from '#/locales';

defineOptions({ name: 'UserLegalDocument' });

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const notFound = ref(false);
const html = ref('');

const kind = computed<'privacy' | 'terms'>(() =>
  route.path.includes('terms') ? 'terms' : 'privacy',
);

const pageTitle = computed(() =>
  kind.value === 'privacy'
    ? $t('user.auth.privacyPolicy')
    : $t('user.auth.termsOfService'),
);

const safeHtml = computed(() => DOMPurify.sanitize(html.value || ''));

onMounted(async () => {
  loading.value = true;
  notFound.value = false;
  try {
    const res = await getTenantLegalDocumentApi(kind.value);
    if (!res?.html?.trim()) {
      notFound.value = true;
      html.value = '';
    } else {
      html.value = res.html;
    }
  } catch {
    notFound.value = true;
    html.value = '';
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="legal-document-template flex min-h-0 flex-1 flex-col">
    <!-- 工具条：返回 -->
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <Button
        type="default"
        class="legal-doc-back !inline-flex items-center gap-1.5 !rounded-full border-border !px-4"
        @click="router.push('/auth/register')"
      >
        <IconifyIcon icon="lucide:arrow-left" class="size-4" />
        {{ $t('user.auth.backToRegister') }}
      </Button>
    </div>

    <!-- 标题区 -->
    <div class="legal-doc-title-wrap mb-6 rounded-2xl bg-gradient-to-br from-primary/[0.06] via-transparent to-violet-500/[0.06] px-5 py-6 sm:px-6 sm:py-8">
      <h1
        class="text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
      >
        {{ pageTitle }}
      </h1>
      <p class="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {{ $t('user.auth.legalDocIntro') }}
      </p>
    </div>

    <!-- 正文纸张 -->
    <Spin :spinning="loading" class="min-h-[12rem] flex-1">
      <div
        v-if="notFound && !loading"
        class="legal-doc-paper rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center text-sm text-muted-foreground"
      >
        <IconifyIcon
          icon="lucide:file-question"
          class="mx-auto mb-3 size-10 opacity-50"
        />
        {{ $t('user.auth.legalNotFound') }}
      </div>

      <article
        v-else-if="!loading"
        class="legal-doc-paper rounded-2xl border border-black/[0.06] bg-white/80 px-5 py-8 shadow-sm dark:border-border dark:bg-card/50 sm:px-8 sm:py-10 lg:px-12 lg:py-12"
      >
        <div
          class="legal-document-body max-w-none text-[15px] leading-[1.75] text-foreground"
          v-html="safeHtml"
        />
      </article>
    </Spin>

    <footer
      class="mt-8 border-t border-black/[0.06] pt-5 text-center text-xs text-muted-foreground dark:border-border"
    >
      {{ $t('user.auth.legalDocFooter') }}
    </footer>
  </div>
</template>

<style scoped>
/* 正文区：法律文档式排版（不依赖 tailwind typography 插件） */
.legal-document-body :deep(h1),
.legal-document-body :deep(h2),
.legal-document-body :deep(h3) {
  margin-top: 1.5em;
  margin-bottom: 0.6em;
  font-weight: 600;
  line-height: 1.35;
  color: hsl(var(--foreground));
}

.legal-document-body :deep(h1) {
  font-size: 1.375rem;
}
.legal-document-body :deep(h2) {
  font-size: 1.2rem;
}
.legal-document-body :deep(h3) {
  font-size: 1.05rem;
}

.legal-document-body :deep(p) {
  margin-bottom: 1em;
}

.legal-document-body :deep(ul),
.legal-document-body :deep(ol) {
  margin: 0.75em 0 1em;
  padding-left: 1.5em;
}

.legal-document-body :deep(li) {
  margin-bottom: 0.35em;
}

.legal-document-body :deep(blockquote) {
  margin: 1em 0;
  border-left: 4px solid hsl(var(--primary) / 0.45);
  padding-left: 1rem;
  color: hsl(var(--muted-foreground));
  font-size: 0.95em;
}

.legal-document-body :deep(table) {
  width: 100%;
  margin: 1em 0;
  border-collapse: collapse;
  font-size: 0.9em;
}

.legal-document-body :deep(th),
.legal-document-body :deep(td) {
  border: 1px solid hsl(var(--border));
  padding: 0.5rem 0.75rem;
  text-align: left;
}

.legal-document-body :deep(th) {
  background: hsl(var(--muted) / 0.35);
  font-weight: 600;
}

.legal-document-body :deep(pre) {
  margin: 1em 0;
  overflow-x: auto;
  border-radius: 0.5rem;
  padding: 1rem;
  background: hsl(var(--muted) / 0.4);
  font-size: 0.875em;
}

.legal-document-body :deep(code) {
  font-size: 0.9em;
}

.legal-document-body :deep(hr) {
  margin: 2em 0;
  border: 0;
  border-top: 1px solid hsl(var(--border));
}

.legal-document-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.5rem;
}

.legal-document-body :deep(a) {
  color: hsl(var(--primary));
  text-decoration: underline;
  text-underline-offset: 2px;
}

.legal-document-body :deep(a:hover) {
  opacity: 0.9;
}
</style>
