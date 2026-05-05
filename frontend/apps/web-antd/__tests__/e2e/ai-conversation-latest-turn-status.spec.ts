/**
 * Test type: smoke
 * Scope: real-browser monitoring conversation status rendering for conversation
 * 2344's active-lifecycle/provider_unavailable latest-turn shape.
 * Mock strategy: no backend or LLM calls; Vite serves a recorded read-model
 * fixture that mounts the real monitoring grid status cell in Chromium.
 */
import { expect, test } from '@playwright/test';

interface ConversationStatusRegressionWindowState {
  activeColor: string;
  activeText: string;
  displayStatus: string;
  failedColor: string;
  failedText: string;
}

declare global {
  interface Window {
    __conversationStatusRegressionReady?: boolean;
    __conversationStatusRegressionState?: ConversationStatusRegressionWindowState;
  }
}

test.describe('AI monitoring latest-turn status regression', () => {
  test('conversation 2344 provider_unavailable displays failed, not in-progress', async ({
    page,
  }) => {
    await page.goto('/');
    await page.setContent(`
      <main id="app"></main>
      <script type="module">
        import { mountConversationStatusRegressionFixture } from '/src/features/ai-monitoring/__tests__/conversation-status-regression-fixture.ts';
        await mountConversationStatusRegressionFixture(document.querySelector('#app'));
      </script>
    `);
    await page.waitForFunction(
      () => window.__conversationStatusRegressionReady === true,
    );

    const state = await page.evaluate(
      () => window.__conversationStatusRegressionState,
    );
    expect(state?.activeColor).toBe('processing');
    expect(state?.displayStatus).toBe('failed');
    expect(state?.failedColor).toBe('error');
    expect(state?.failedText.toLowerCase()).toContain('failed');

    const failedStatus = page.getByTestId('conversation-2344-status');
    await expect(failedStatus).toContainText(/failed/i);
    await expect(failedStatus).not.toContainText('active');
    await expect(failedStatus).not.toContainText('进行中');
  });
});
