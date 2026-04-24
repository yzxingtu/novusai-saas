// Test type: smoke
// Verifies: admin, tenant, and user AI chat surfaces share the transcript-first
// shell, keep diagnostics gated, and expose avatar profile details after a real SSE turn.
import type { Locator, Page } from '@playwright/test';

import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';
import { hasTenantCredentials, loginAsTenant } from './common/auth';
import { interceptChatSSE } from './common/sse-helpers';
import { hasUserCredentials, loginAsUser } from './common/user-auth';

const adminEnabled = hasAdminCredentials();
const tenantEnabled = hasTenantCredentials();
const userEnabled = hasUserCredentials();

const CHAT_TIMEOUT = 120_000;
const TEST_TIMEOUT = CHAT_TIMEOUT + 60_000;
const CHAT_INPUT_SELECTOR = '[data-testid="ai-chat-input"]';
const COMMAND_INPUT_SELECTOR =
  'textarea[placeholder*="输入消息"], textarea[placeholder*="Enter"]';
const DIAGNOSTIC_LABELS = [
  '结束原因',
  '协议路径',
  '本轮工具',
  '本轮技能',
  '上下文来源',
] as const;

function latestAssistantSurface(page: Page) {
  return page.locator('.assistant-message-surface').last();
}

function getVisibleComposer(page: Page, dedicatedUserPage = false) {
  if (dedicatedUserPage) {
    return page.locator(CHAT_INPUT_SELECTOR).last();
  }
  return page.locator(CHAT_INPUT_SELECTOR).first();
}

async function expectGracefulResponse(fullResponse: string, errors: string[]) {
  expect(errors).toHaveLength(0);
  expect(fullResponse.trim().length).toBeGreaterThan(2);
  expect(fullResponse).not.toContain('[PARTIAL EXIT]');
  expect(fullResponse).not.toMatch(
    /Traceback|Internal Server Error|Unhandled/i,
  );
}

async function expectTranscriptFirst(surface: Locator) {
  const kernelHeader = surface
    .locator('[data-testid="chat-message-kernel-header"]')
    .first();
  const transcript = surface.locator('.assistant-message-body').first();

  await expect(kernelHeader).toBeVisible({ timeout: 10_000 });
  await expect(transcript).toBeVisible({ timeout: 10_000 });

  const rendersKernelBeforeTranscript = await surface.evaluate((element) => {
    const kernel = element.querySelector(
      '[data-testid="chat-message-kernel-header"]',
    );
    const body = element.querySelector('.assistant-message-body');
    if (!(kernel instanceof HTMLElement) || !(body instanceof HTMLElement)) {
      return false;
    }
    return (
      (kernel.compareDocumentPosition(body) &
        Node.DOCUMENT_POSITION_FOLLOWING) >
      0
    );
  });

  expect(
    rendersKernelBeforeTranscript,
    'Expected process header to render before transcript content in DOM order',
  ).toBe(true);
}

async function expectDiagnosticsHiddenByDefault(surface: Locator) {
  const surfaceText = (await surface.textContent()) ?? '';
  for (const label of DIAGNOSTIC_LABELS) {
    expect(
      surfaceText.includes(label),
      `Expected diagnostics label "${label}" to stay hidden by default.`,
    ).toBe(false);
  }
}

async function expectAgentProfilePopover(page: Page) {
  const avatar = page.locator('[data-testid="assistant-agent-avatar"]').last();
  await expect(avatar).toBeVisible({ timeout: 10_000 });
  await avatar.click();

  await expect(
    page.locator('[data-testid="agent-profile-skills-section"]').last(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.locator('[data-testid="agent-profile-kb-section"]').last(),
  ).toBeVisible({ timeout: 10_000 });

  await expect(
    page
      .locator(
        '[data-testid="agent-profile-skill-package-chip"], [data-testid="agent-profile-skill-empty"]',
      )
      .first(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page
      .locator(
        '[data-testid="agent-profile-skill-entry-chip"], [data-testid="agent-profile-skill-entry-empty"]',
      )
      .first(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page
      .locator(
        '[data-testid="agent-profile-kb-chip"], [data-testid="agent-profile-kb-empty"]',
      )
      .first(),
  ).toBeVisible({ timeout: 10_000 });
}

async function ensureSlidePanelOpen(page: Page) {
  const panelInput = page.locator(CHAT_INPUT_SELECTOR);
  if (await panelInput.isVisible().catch(() => false)) {
    return;
  }

  const commandInput = page.locator(COMMAND_INPUT_SELECTOR).first();
  if (await commandInput.isVisible().catch(() => false)) {
    return;
  }

  const trigger = page
    .locator(
      'xpath=//div[contains(@class,"cursor-pointer")][contains(normalize-space(.),"AI 助手")]',
    )
    .first();

  await ((await trigger.isVisible().catch(() => false))
    ? trigger.click()
    : page.keyboard.press('Control+k').catch(() => undefined));

  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    if (
      (await panelInput.isVisible().catch(() => false)) ||
      (await commandInput.isVisible().catch(() => false))
    ) {
      return;
    }
    await page.waitForTimeout(200);
  }

  throw new Error('Timed out waiting for the AI composer to appear.');
}

async function submitPrompt(
  page: Page,
  prompt: string,
  options: { dedicatedUserPage?: boolean } = {},
) {
  const waitForChat = await interceptChatSSE(page);
  const panelComposer = getVisibleComposer(page, options.dedicatedUserPage);

  if (
    options.dedicatedUserPage ||
    (await panelComposer.isVisible().catch(() => false))
  ) {
    await expect(panelComposer).toBeVisible({ timeout: 15_000 });
    await expect(panelComposer).toBeEnabled({ timeout: 15_000 });
    await panelComposer.click();
    await panelComposer.fill(prompt);
    await panelComposer.press('Enter');
    return waitForChat({ timeout: CHAT_TIMEOUT });
  }

  const commandComposer = page.locator(COMMAND_INPUT_SELECTOR).first();
  await expect(commandComposer).toBeVisible({ timeout: 15_000 });
  await expect(commandComposer).toBeEnabled({ timeout: 15_000 });
  await commandComposer.click();
  await commandComposer.fill(prompt);
  await commandComposer.press('Enter');
  return waitForChat({ timeout: CHAT_TIMEOUT });
}

async function assertSharedAssistantShell(page: Page) {
  const assistantSurface = latestAssistantSurface(page);
  const processBody = assistantSurface.locator(
    '[data-testid="turn-process-body"]',
  );

  await expect(assistantSurface).toBeVisible({ timeout: 10_000 });
  await expectTranscriptFirst(assistantSurface);
  await expectDiagnosticsHiddenByDefault(assistantSurface);
  await expect(processBody).toHaveAttribute(
    'style',
    /grid-template-rows:\s*0fr/i,
    { timeout: 10_000 },
  );
  await expectAgentProfilePopover(page);
}

test.describe('AI Chat shell cross-surface smoke', () => {
  test.describe.configure({ timeout: TEST_TIMEOUT });

  test('admin surface keeps transcript-first shell and avatar details', async ({
    page,
  }) => {
    test.skip(!adminEnabled, 'Admin credentials are not configured');

    await loginAsAdmin(page);
    await page.goto('/admin/ai/agents');
    await page.waitForLoadState('networkidle');
    await ensureSlidePanelOpen(page);

    const metrics = await submitPrompt(page, '现在几点了？请只用一句话回答。');

    await expectGracefulResponse(metrics.fullResponse, metrics.errors);
    await assertSharedAssistantShell(page);
  });

  test('tenant surface keeps transcript-first shell and avatar details', async ({
    page,
  }) => {
    test.skip(!tenantEnabled, 'Tenant credentials are not configured');

    await loginAsTenant(page);
    await page.goto('/tenant/dashboard');
    await page.waitForLoadState('networkidle');
    await ensureSlidePanelOpen(page);

    const metrics = await submitPrompt(page, '现在几点了？请只用一句话回答。');

    await expectGracefulResponse(metrics.fullResponse, metrics.errors);
    await assertSharedAssistantShell(page);
  });

  test('user workspace keeps transcript-first shell and avatar details', async ({
    page,
  }) => {
    test.skip(!userEnabled, 'User credentials are not configured');

    await loginAsUser(page);
    await page.goto('/ai-chat');
    await page.waitForLoadState('networkidle');

    const metrics = await submitPrompt(page, '现在几点了？请只用一句话回答。', {
      dedicatedUserPage: true,
    });

    await expectGracefulResponse(metrics.fullResponse, metrics.errors);
    await assertSharedAssistantShell(page);
  });
});
