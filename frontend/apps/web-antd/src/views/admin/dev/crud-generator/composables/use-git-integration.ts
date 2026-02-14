/**
 * Git Integration — Git 集成 + 自动 E2E 测试生成
 *
 * 职责:
 * 1. 生成 Git commit message (conventional commits)
 * 2. 生成 .gitignore 条目
 * 3. 自动生成 E2E 测试文件 (Playwright)
 */

import type { CrudConfig } from '../types';

// ============================================================
// Git commit message generation
// ============================================================

/**
 * 生成 conventional commit message
 */
export function generateCommitMessage(config: CrudConfig, isNew: boolean): string {
  const module = config.module;
  const scope = config.scope;

  if (isNew) {
    return `feat(${module}): add ${config.display_name_en || module} CRUD module

- Add ${scope} backend: model, repository, service, controller
- Add ${scope} frontend: list page, form drawer, data.ts
- Add i18n keys (zh-CN, en-US)
- Add ${config.fields.length} fields, ${config.enums.length} enums
${config.relations.length > 0 ? `- Add ${config.relations.length} relations` : ''}
${config.recyclable ? '- Enable recycle bin' : ''}
${config.soft_delete ? '- Enable soft delete' : ''}`;
  }

  return `refactor(${module}): update ${config.display_name_en || module} CRUD configuration

- Updated via CRUD Generator incremental generation`;
}

/**
 * 生成 branch name
 */
export function generateBranchName(config: CrudConfig): string {
  return `feat/crud-${config.module}`;
}

// ============================================================
// E2E test generation (Playwright)
// ============================================================

/**
 * 生成 Playwright E2E 测试文件
 */
export function generateE2ETest(config: CrudConfig): string {
  const module = config.module;
  const displayName = config.display_name_en || config.display_name || module;
  const scope = config.scope === 'admin' ? 'admin' : 'tenant';
  const routePath = `/${scope}/${module}`;

  const lines: string[] = [];

  lines.push(`import { expect, test } from '@playwright/test';`);
  lines.push(``);
  lines.push(`test.describe('${displayName} CRUD', () => {`);
  lines.push(`  test.beforeEach(async ({ page }) => {`);
  lines.push(`    // Login and navigate`);
  lines.push(`    await page.goto('${routePath}');`);
  lines.push(`    await page.waitForLoadState('networkidle');`);
  lines.push(`  });`);
  lines.push(``);

  // List page test
  lines.push(`  test('should display list page', async ({ page }) => {`);
  lines.push(`    await expect(page.locator('.vxe-table')).toBeVisible();`);
  lines.push(`  });`);
  lines.push(``);

  // Create test
  if (config.operations.includes('edit')) {
    lines.push(`  test('should create new ${module}', async ({ page }) => {`);
    lines.push(`    await page.getByRole('button', { name: /create|新建/ }).click();`);
    lines.push(`    await page.waitForSelector('.ant-drawer');`);

    const requiredFields = config.fields.filter(
      (f) => f.required && f.in_form && !['id', 'created_at', 'updated_at'].includes(f.name),
    );

    for (const field of requiredFields.slice(0, 3)) {
      if (field.form_component === 'Input' || field.form_component === 'Textarea') {
        lines.push(`    await page.getByLabel('${field.label_en || field.label_zh || field.name}').fill('Test ${field.name}');`);
      } else if (field.form_component === 'Select') {
        lines.push(`    await page.getByLabel('${field.label_en || field.label_zh || field.name}').click();`);
        lines.push(`    await page.locator('.ant-select-dropdown .ant-select-item').first().click();`);
      }
    }

    lines.push(`    await page.getByRole('button', { name: /submit|提交/ }).click();`);
    lines.push(`    await expect(page.locator('.ant-message-success')).toBeVisible();`);
    lines.push(`  });`);
    lines.push(``);
  }

  // Search test
  if (config.list_config.toolbar_search) {
    lines.push(`  test('should search ${module}s', async ({ page }) => {`);
    lines.push(`    const searchInput = page.locator('.vxe-toolbar input[type="text"]').first();`);
    lines.push(`    await searchInput.fill('test');`);
    lines.push(`    await searchInput.press('Enter');`);
    lines.push(`    await page.waitForLoadState('networkidle');`);
    lines.push(`  });`);
    lines.push(``);
  }

  // Delete test
  if (config.operations.includes('delete')) {
    lines.push(`  test('should delete ${module}', async ({ page }) => {`);
    lines.push(`    const row = page.locator('.vxe-body--row').first();`);
    lines.push(`    await row.locator('button[title="delete"], button[title="删除"]').click();`);
    lines.push(`    await page.getByRole('button', { name: /ok|确定/ }).click();`);
    lines.push(`    await expect(page.locator('.ant-message-success')).toBeVisible();`);
    lines.push(`  });`);
  }

  lines.push(`});`);

  return lines.join('\n');
}

/**
 * 生成测试文件路径
 */
export function getE2ETestPath(config: CrudConfig): string {
  return `tests/e2e/${config.scope}/${config.module}.spec.ts`;
}

/**
 * 生成所有 Git 相关输出
 */
export function generateGitArtifacts(config: CrudConfig, isNew: boolean) {
  return {
    commitMessage: generateCommitMessage(config, isNew),
    branchName: generateBranchName(config),
    e2eTest: generateE2ETest(config),
    e2eTestPath: getE2ETestPath(config),
  };
}
