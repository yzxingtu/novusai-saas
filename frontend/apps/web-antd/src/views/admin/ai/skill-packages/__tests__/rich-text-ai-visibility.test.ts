// 中文: 测试类型：structural。
// EN: Test type: structural.
// 中文: 范围：技能包管理不得暴露独立的 Rich Text AI 运行时配置界面。
// EN: Scope: Skill package management must not expose a separate Rich Text AI runtime configuration surface.
// 中文: Mock 策略：不使用 mock，直接读取源码和 locale JSON 作为静态 UI 契约。
// EN: Mock strategy: No mocks; this test reads source and locale JSON as static UI contracts.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const currentDir = dirname(fileURLToPath(import.meta.url));
const skillPackagesDir = resolve(currentDir, '..');
const repoSrcDir = resolve(skillPackagesDir, '../../../..');

function readSkillPackageSource(relativePath: string): string {
  return readFileSync(resolve(skillPackagesDir, relativePath), 'utf8');
}

function readAdminAiLocale(locale: 'en-US' | 'zh-CN') {
  const content = readFileSync(
    resolve(repoSrcDir, `locales/langs/${locale}/admin/ai.json`),
    'utf8',
  );
  return JSON.parse(content) as {
    skillPackage: {
      richTextAi?: Record<string, unknown>;
    };
  };
}

describe('skill package rich text ai visibility contract', () => {
  it('does not expose a dedicated Rich Text AI tab, button, or route query from skill packages', () => {
    const detail = readSkillPackageSource('detail.vue');
    const list = readSkillPackageSource('index.vue');
    const panel = readSkillPackageSource('modules/SkillPackageDetailPanel.vue');
    const actions = readSkillPackageSource('use-skill-package-actions.ts');

    expect(detail).not.toContain('SkillPackageRichTextAiTab');
    expect(detail).not.toContain('key="richTextAi"');
    expect(list).not.toContain('on-open-rich-text-ai-config');
    expect(panel).not.toContain('onOpenRichTextAiConfig');
    expect(panel).not.toContain('admin.ai.skillPackage.richTextAi.configBtn');
    expect(actions).not.toContain('goToRichTextAiConfig');
    expect(actions).not.toContain("tab: 'richTextAi'");
    expect(
      existsSync(resolve(skillPackagesDir, 'modules/detail/SkillPackageRichTextAiTab.vue')),
    ).toBe(false);
  });

  it('keeps system.ai_writing wording but does not describe plugin.novusdoc.rich_text_ai as a runtime feature', () => {
    for (const locale of ['zh-CN', 'en-US'] as const) {
      const richTextAi = readAdminAiLocale(locale).skillPackage.richTextAi;
      const serialized = JSON.stringify(richTextAi ?? {});

      expect(serialized).toContain('system.ai_writing');
      expect(serialized).not.toContain('plugin.novusdoc.rich_text_ai');
      expect(richTextAi?.configBtn).not.toBe('富文本 AI');
      expect(richTextAi?.configBtn).not.toBe('Rich Text AI');
      expect(richTextAi?.tab).not.toBe('富文本 AI');
      expect(richTextAi?.tab).not.toBe('Rich Text AI');
    }
  });
});
