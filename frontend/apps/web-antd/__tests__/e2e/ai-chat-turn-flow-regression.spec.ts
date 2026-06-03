/**
 * Test type: behavioral
 * Scope: real-browser rendering of the AI chat kernel for conversation 2340's
 * provider-failure turn-flow shape.
 * Mock strategy: no backend or LLM calls; Vite serves a fixture page that mounts
 * the real Vue component and real turn-flow state builder in Chromium.
 */
import { expect, test } from '@playwright/test';

interface TurnFlowRegressionWindowState {
  answerChipCount: number;
  evidenceCount: number;
  finalStageStatus: null | string;
  retrievalSourceCount: null | number;
  retrievalStatus: null | string;
  selectedEvidenceCount: number;
}

declare global {
  interface Window {
    __turnFlowRegressionReady?: boolean;
    __turnFlowRegressionState?: TurnFlowRegressionWindowState;
  }
}

test.describe('AI chat turn-flow context-source regression', () => {
  test('conversation 2340 provider failure does not render fake source chrome', async ({
    page,
  }) => {
    await page.goto('/');
    await page.setContent(`
      <main id="app"></main>
      <script type="module">
        import { mountTurnFlowContextSourceRegressionFixture } from '/src/components/business/ai-chat-kernel/__tests__/turn-flow-context-source-regression-fixture.ts';
        await mountTurnFlowContextSourceRegressionFixture(document.querySelector('#app'));
      </script>
    `);
    await page.waitForFunction(() => window.__turnFlowRegressionReady === true);

    const state = await page.evaluate(() => window.__turnFlowRegressionState);
    expect(state).toEqual({
      answerChipCount: 0,
      evidenceCount: 0,
      finalStageStatus: 'error',
      retrievalSourceCount: 0,
      retrievalStatus: 'skipped',
      selectedEvidenceCount: 0,
    });

    const app = page.locator('#app');
    await expect(app).toContainText('Connection error.');
    await expect(app).not.toContainText('Retrieved 3 sources');
    await expect(app).not.toContainText('找到 3 条来源');
    await expect(app).not.toContainText('skill_resolver');
    await expect(app).not.toContainText('long_term_memory');
    await expect(app).not.toContainText('gpt-5.5');

    await page.getByTestId('chat-message-kernel-overview-toggle').click();
    await expect(page.getByTestId('chat-message-kernel-body')).toBeVisible();
    await expect(app).not.toContainText('Retrieved 3 sources');
    await expect(app).not.toContainText('找到 3 条来源');
    await expect(app).not.toContainText('skill_resolver');
    await expect(app).not.toContainText('long_term_memory');
    await expect(app).not.toContainText('gpt-5.5');
  });
});
