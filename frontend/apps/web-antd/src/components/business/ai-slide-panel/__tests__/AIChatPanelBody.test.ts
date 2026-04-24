// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
/**
 * Test type: behavioral
 * Verifies: the shared admin/tenant panel body forwards message-agent knowledge-base / skill bindings
 * and the loader callbacks into the shared message viewport without falling back to selected-agent-only data.
 * Mock strategy: child layout blocks are stubbed, while AIChatPanelBody prop wiring runs real.
 */
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatPanelBody from '../AIChatPanelBody.vue';

describe('AIChatPanelBody', () => {
  it('forwards message-agent knowledge-base bindings into the shared viewport chain', () => {
    const ensureAgentKnowledgeBases = vi.fn(async () => []);
    const ensureAgentSkills = vi.fn(async () => []);

    const wrapper = mount(AIChatPanelBody, {
      props: {
        apiPrefix: '/admin',
        agentKnowledgeBases: [
          {
            enabled: true,
            id: 701,
            kb_name: '当前选中知识库',
            knowledge_base_id: 701,
          },
        ],
        agentKnowledgeBaseMap: {
          9: [
            {
              enabled: true,
              id: 301,
              kb_name: '历史消息知识库',
              knowledge_base_id: 301,
            },
          ],
        },
        agentSkillMap: {
          9: [
            {
              enabled: true,
              id: 901,
              package_name: '历史技能包',
              skill_id: 1901,
              skill_name: '历史技能',
            },
          ],
        },
        chatMessages: [
          {
            agent_id: 9,
            clientKey: 'assistant-routed-kb',
            content: '历史 routed 消息',
            role: 'assistant',
          },
        ],
        ensureAgentKnowledgeBases,
        ensureAgentSkills,
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        selectedAgent: {
          avatar: null,
          description: null,
          id: 7,
          knowledge_bases: [
            {
              enabled: true,
              id: 701,
              kb_name: '当前选中知识库',
              knowledge_base_id: 701,
            },
          ],
          name: '当前选中智能体',
          skills: [],
          status: 'published',
          tenant_id: 1,
        },
      },
      global: {
        stubs: {
          AIChatComposer: defineComponent({
            name: 'AIChatComposerStub',
            template: '<div data-testid="composer-stub" />',
          }),
          AIChatConversationFooter: defineComponent({
            name: 'AIChatConversationFooterStub',
            template: '<div data-testid="conversation-footer-stub" />',
          }),
          AIChatHistoryPane: defineComponent({
            name: 'AIChatHistoryPaneStub',
            template: '<div data-testid="history-pane-stub" />',
          }),
          AIChatMessageViewport: defineComponent({
            name: 'AIChatMessageViewportProbe',
            props: {
              agentKnowledgeBaseMap: { type: Object, required: false },
              agentSkillMap: { type: Object, required: false },
              chatMessages: { type: Array, required: false },
              ensureAgentKnowledgeBases: {
                type: Function,
                required: false,
              },
              ensureAgentSkills: {
                type: Function,
                required: false,
              },
            },
            template:
              '<div data-testid="viewport-probe" :data-agent-id="String(chatMessages?.[0]?.agent_id || \'\')" :data-kb-name="String(agentKnowledgeBaseMap?.[9]?.[0]?.kb_name || \'\')" :data-skill-name="String(agentSkillMap?.[9]?.[0]?.skill_name || \'\')" :data-has-kb-ensure="String(typeof ensureAgentKnowledgeBases === \'function\')" :data-has-skill-ensure="String(typeof ensureAgentSkills === \'function\')" />',
          }),
        },
      },
    });

    const viewport = wrapper.get('[data-testid="viewport-probe"]');
    expect(viewport.attributes('data-agent-id')).toBe('9');
    expect(viewport.attributes('data-kb-name')).toBe('历史消息知识库');
    expect(viewport.attributes('data-skill-name')).toBe('历史技能');
    expect(viewport.attributes('data-has-kb-ensure')).toBe('true');
    expect(viewport.attributes('data-has-skill-ensure')).toBe('true');
  });
});
