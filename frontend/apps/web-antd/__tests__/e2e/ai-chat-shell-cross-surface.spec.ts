// Test type: smoke
// Verifies: admin, tenant, and user AI chat surfaces share the transcript-first
// shell, keep diagnostics gated, expose avatar profile details after a real SSE turn,
// and invalid runtime tools stay absent from ordinary chat turns.
import type { Locator, Page } from '@playwright/test';

import type { ChatTurnMetrics } from './common/sse-helpers';

import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';
import {
  buildLocaleVariantPattern,
  includesLocaleVariant,
  sharedAIChatCopyContract,
} from './common/ai-chat-copy-contract';
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
const DIAGNOSTIC_LABEL_VARIANTS = [
  sharedAIChatCopyContract.diagnosticTerminationReasonLabel,
  sharedAIChatCopyContract.diagnosticProtocolPathLabel,
  sharedAIChatCopyContract.diagnosticSelectedToolsLabel,
  sharedAIChatCopyContract.diagnosticSelectedSkillsLabel,
  sharedAIChatCopyContract.diagnosticContextSourcesLabel,
] as const;
const HEADER_DIAGNOSTIC_MENU_VARIANTS = [
  sharedAIChatCopyContract.headerShowDiagnostics,
  sharedAIChatCopyContract.headerRunTimeline,
  sharedAIChatCopyContract.headerRefreshContext,
] as const;
const BLOCKED_RUNTIME_TOOL_PREFIX = `${'u'}${'i'}_`;
const HEADER_NEW_CHAT_PATTERN = buildLocaleVariantPattern(
  sharedAIChatCopyContract.headerNewChat,
);
const HEADER_MEMORY_PATTERN = buildLocaleVariantPattern(
  sharedAIChatCopyContract.headerMemory,
);
const HEADER_MORE_ACTIONS_PATTERN = buildLocaleVariantPattern(
  sharedAIChatCopyContract.headerMoreActions,
);

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

function expectNoBlockedRuntimeTool(metrics: ChatTurnMetrics, message: string) {
  const seenToolNames = metrics.toolCalls.map(({ name }) => name);
  expect(
    metrics.toolCalls.some((toolCall) =>
      toolCall.name.startsWith(BLOCKED_RUNTIME_TOOL_PREFIX),
    ),
    `${message}. Seen tool calls: ${seenToolNames.join(', ') || 'none'}`,
  ).toBe(false);
}

async function expectTranscriptFirst(surface: Locator) {
  const kernelHeader = surface
    .locator('[data-testid="chat-message-kernel-header"]')
    .first();
  const transcript = surface
    .locator('.assistant-message-body, .assistant-content-block')
    .first();

  await expect(kernelHeader).toBeVisible({ timeout: 10_000 });
  await expect(transcript).toBeVisible({ timeout: 10_000 });

  await expect
    .poll(
      async () =>
        surface.evaluate((surfaceElement) => {
          const kernelHeaderElement = surfaceElement.querySelector(
            '[data-testid="chat-message-kernel-header"]',
          );
          const transcriptElement = surfaceElement.querySelector(
            '.assistant-message-body, .assistant-content-block',
          );

          if (
            !(kernelHeaderElement instanceof HTMLElement) ||
            !(transcriptElement instanceof HTMLElement)
          ) {
            return null;
          }

          const kernelBox = kernelHeaderElement.getBoundingClientRect();
          const transcriptBox = transcriptElement.getBoundingClientRect();

          return {
            hasKernelBox: kernelBox.height > 0 && kernelBox.width > 0,
            hasTranscriptBox:
              transcriptBox.height > 0 && transcriptBox.width > 0,
            transcriptFirst: kernelBox.top > transcriptBox.top,
          };
        }),
      { timeout: 10_000 },
    )
    .toEqual({
      hasKernelBox: true,
      hasTranscriptBox: true,
      transcriptFirst: true,
    });
}

async function expectDiagnosticsHiddenByDefault(surface: Locator) {
  const surfaceText = (await surface.textContent()) ?? '';
  for (const variants of DIAGNOSTIC_LABEL_VARIANTS) {
    expect(
      includesLocaleVariant(surfaceText, variants),
      `Expected diagnostics label variants "${variants.join(' / ')}" to stay hidden by default.`,
    ).toBe(false);
  }
}

async function hasVisibleButton(page: Page, name: RegExp) {
  const buttons = page.getByRole('button', { name });
  const count = await buttons.count().catch(() => 0);

  for (let index = 0; index < count; index += 1) {
    if (
      await buttons
        .nth(index)
        .isVisible()
        .catch(() => false)
    ) {
      return true;
    }
  }

  return false;
}

async function expectSharedHeaderCopy(
  page: Page,
  options: { expectMoreActions: boolean },
) {
  expect(
    await hasVisibleButton(page, HEADER_NEW_CHAT_PATTERN),
    `Expected shared new-chat copy variants: ${sharedAIChatCopyContract.headerNewChat.join(' / ')}`,
  ).toBe(true);
  expect(
    await hasVisibleButton(page, HEADER_MEMORY_PATTERN),
    `Expected shared memory copy variants: ${sharedAIChatCopyContract.headerMemory.join(' / ')}`,
  ).toBe(true);

  if (options.expectMoreActions) {
    expect(
      await hasVisibleButton(page, HEADER_MORE_ACTIONS_PATTERN),
      `Expected shared more-actions copy variants: ${sharedAIChatCopyContract.headerMoreActions.join(' / ')}`,
    ).toBe(true);
  }
}

async function expectHeaderDiagnosticsHiddenByDefault(page: Page) {
  const moreButton = page.getByRole('button', {
    name: HEADER_MORE_ACTIONS_PATTERN,
  });
  if (
    !(await moreButton
      .first()
      .isVisible()
      .catch(() => false))
  ) {
    return;
  }

  await moreButton.first().click();
  const menu = page.locator('.ant-dropdown').last();
  if (await menu.isVisible().catch(() => false)) {
    const menuText = (await menu.textContent()) ?? '';
    for (const variants of HEADER_DIAGNOSTIC_MENU_VARIANTS) {
      expect(
        includesLocaleVariant(menuText, variants),
        `Expected header diagnostics entry variants "${variants.join(' / ')}" to stay hidden by default.`,
      ).toBe(false);
    }
  }
  await page.keyboard.press('Escape').catch(() => undefined);
}

async function expectAgentProfilePopover(page: Page) {
  const avatar = page.locator('[data-testid="assistant-agent-avatar"]').last();
  const popover = page.locator('[data-testid="agent-profile-popover-content"]');
  const skillSection = page.locator(
    '[data-testid="agent-profile-skills-section"]',
  );
  const kbSection = page.locator('[data-testid="agent-profile-kb-section"]');
  await expect(avatar).toBeVisible({ timeout: 10_000 });
  await avatar.hover().catch(() => undefined);

  let popoverVisible = false;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await avatar.click();
    try {
      await expect(skillSection.last()).toBeVisible({ timeout: 4000 });
      await expect(kbSection.last()).toBeVisible({ timeout: 4000 });
      popoverVisible = true;
      break;
    } catch (error) {
      if (attempt === 2) {
        throw error;
      }
      await page.waitForTimeout(400);
      await avatar.hover().catch(() => undefined);
    }
  }
  expect(popoverVisible).toBe(true);
  await expect(popover.last()).toBeVisible({ timeout: 10_000 });

  const popoverText = (await popover.last().textContent()) ?? '';
  expect(
    includesLocaleVariant(
      popoverText,
      sharedAIChatCopyContract.agentProfileSkillPackages,
    ),
    `Expected shared skill-packages label variants: ${sharedAIChatCopyContract.agentProfileSkillPackages.join(' / ')}`,
  ).toBe(true);
  expect(
    includesLocaleVariant(
      popoverText,
      sharedAIChatCopyContract.agentProfileSkillEntries,
    ),
    `Expected shared skill-entries label variants: ${sharedAIChatCopyContract.agentProfileSkillEntries.join(' / ')}`,
  ).toBe(true);
  expect(
    includesLocaleVariant(
      popoverText,
      sharedAIChatCopyContract.agentProfileKnowledgeBases,
    ),
    `Expected shared knowledge-base label variants: ${sharedAIChatCopyContract.agentProfileKnowledgeBases.join(' / ')}`,
  ).toBe(true);
  expect(
    includesLocaleVariant(
      popoverText,
      sharedAIChatCopyContract.agentProfileHint,
    ),
    `Expected shared profile-hint variants: ${sharedAIChatCopyContract.agentProfileHint.join(' / ')}`,
  ).toBe(true);

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
  await expect(
    page.locator('[data-testid="agent-profile-description"]').last(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.locator('[data-testid="agent-profile-footer"]').last(),
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

async function assertSharedAssistantShell(
  page: Page,
  options: { expectMoreActions: boolean },
) {
  const assistantSurface = latestAssistantSurface(page);
  const overviewToggle = assistantSurface.locator(
    '[data-testid="chat-message-kernel-overview-toggle"]',
  );
  const processBody = assistantSurface.locator(
    '[data-testid="turn-process-body"]',
  );

  await expect(assistantSurface).toBeVisible({ timeout: 10_000 });
  await expectTranscriptFirst(assistantSurface);
  await expectSharedHeaderCopy(page, options);
  await expectDiagnosticsHiddenByDefault(assistantSurface);
  await expectHeaderDiagnosticsHiddenByDefault(page);
  await ((await overviewToggle.count())
    ? expect(overviewToggle).toHaveAttribute('aria-expanded', 'false', {
        timeout: 10_000,
      })
    : expect(processBody).toHaveAttribute(
        'style',
        /grid-template-rows:\s*0fr/i,
        { timeout: 10_000 },
      ));
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
    await assertSharedAssistantShell(page, { expectMoreActions: true });
  });

  test('admin surface avoids invalid runtime tools on list-related chat', async ({
    page,
  }) => {
    test.skip(!adminEnabled, 'Admin credentials are not configured');

    await loginAsAdmin(page);
    await page.goto('/admin/ai/models');
    await page.waitForLoadState('networkidle');
    await ensureSlidePanelOpen(page);

    const metrics = await submitPrompt(
      page,
      '请介绍一下模型管理通常用于哪些配置，只用两句话回答。',
    );

    await expectGracefulResponse(metrics.fullResponse, metrics.errors);
    expectNoBlockedRuntimeTool(
      metrics,
      'Expected invalid runtime tools to stay unavailable for admin list-related chat',
    );
    await assertSharedAssistantShell(page, { expectMoreActions: true });
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
    await assertSharedAssistantShell(page, { expectMoreActions: true });
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
    await assertSharedAssistantShell(page, { expectMoreActions: false });
  });
});
