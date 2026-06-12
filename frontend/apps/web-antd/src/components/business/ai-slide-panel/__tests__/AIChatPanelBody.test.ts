// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
/**
 * Test type: behavioral
 * Verifies: the shared admin/tenant panel body forwards message-agent knowledge-base / skill bindings
 * and the loader callbacks into the shared message viewport without falling back to selected-agent-only data,
 * while keeping the transcript shell mounted when history opens as an overlay.
 * Mock strategy: child layout blocks are stubbed, while AIChatPanelBody prop wiring runs real.
 */
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatPanelBody from '../AIChatPanelBody.vue';

describe('ai chat panel body', () => {
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
              agentKnowledgeBaseMap: {
                type: Object,
                required: false,
                default: () => ({}),
              },
              agentSkillMap: {
                type: Object,
                required: false,
                default: () => ({}),
              },
              chatMessages: {
                type: Array,
                required: false,
                default: () => [],
              },
              ensureAgentKnowledgeBases: {
                type: Function,
                required: false,
                default: undefined,
              },
              ensureAgentSkills: {
                type: Function,
                required: false,
                default: undefined,
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

  it('keeps the transcript mounted and inert while history is shown as a solid overlay', () => {
    const wrapper = mount(AIChatPanelBody, {
      props: {
        apiPrefix: '/admin',
        chatMessages: [
          {
            clientKey: 'assistant-history-overlay',
            content: '当前会话内容',
            role: 'assistant',
          },
        ],
        groupedConversations: [
          {
            label: '今天',
            items: [{ id: 11, title: '会话 11' }],
          },
        ],
        showHistory: true,
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
            name: 'AIChatMessageViewportStub',
            template: '<div data-testid="viewport-probe" />',
          }),
        },
      },
    });

    expect(wrapper.find('[data-testid="viewport-probe"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="composer-stub"]').exists()).toBe(true);
    expect(
      wrapper.find('[data-testid="conversation-footer-stub"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="history-overlay"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="history-pane-stub"]').exists()).toBe(
      true,
    );
    expect(wrapper.find('[data-testid="history-overlay-pane"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.get('[data-testid="history-overlay-pane"]').classes(),
    ).not.toContain('bg-card/92');
    expect(
      wrapper.get('[data-testid="transcript-shell"]').attributes('aria-hidden'),
    ).toBe('true');
    expect(
      wrapper.get('[data-testid="transcript-shell"]').attributes('inert'),
    ).toBe('');
    expect(wrapper.get('[data-testid="transcript-shell"]').classes()).toContain(
      'pointer-events-none',
    );
    expect(wrapper.get('[data-testid="transcript-shell"]').classes()).toContain(
      'opacity-0',
    );
    expect(
      wrapper.get('[data-testid="transcript-shell"]').classes(),
    ).not.toContain('blur-[1px]');
  });

  it('forwards welcome loading state and disables the composer while welcome is being generated', async () => {
    const wrapper = mount(AIChatPanelBody, {
      props: {
        agents: [
          {
            avatar: null,
            description: null,
            id: 1,
            name: 'Copilot',
            status: 'published',
            tenant_id: 1,
          },
        ],
        apiPrefix: '/tenant',
        attachDisabled: false,
        inputMessage: '用户草稿',
        selectedAgent: {
          avatar: '42',
          description: null,
          id: 1,
          name: 'Copilot',
          status: 'published',
          tenant_id: 1,
        },
        sendDisabled: false,
        sending: false,
        welcomeLoading: true,
        welcomeLoadingHint: 'Copilot 正在准备开场建议',
      },
      global: {
        stubs: {
          AIChatComposer: defineComponent({
            name: 'AIChatComposerProbe',
            emits: ['send'],
            props: {
              attachDisabled: { type: Boolean, required: false },
              disabled: { type: Boolean, required: false },
              sendDisabled: { type: Boolean, required: false },
            },
            template:
              '<button data-testid="composer-probe" :data-disabled="String(disabled)" :data-send-disabled="String(sendDisabled)" :data-attach-disabled="String(attachDisabled)" @click="$emit(\'send\')" />',
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
              selectedAgent: {
                type: Object,
                required: false,
                default: null,
              },
              welcomeLoading: {
                type: Boolean,
                required: false,
              },
              welcomeLoadingHint: {
                type: String,
                required: false,
                default: '',
              },
            },
            template:
              '<div data-testid="viewport-welcome-probe" :data-welcome-loading="String(welcomeLoading)" :data-agent-name="String(selectedAgent?.name || \'\')" :data-welcome-hint="welcomeLoadingHint" />',
          }),
        },
      },
    });

    const viewport = wrapper.get('[data-testid="viewport-welcome-probe"]');
    expect(viewport.attributes('data-welcome-loading')).toBe('true');
    expect(viewport.attributes('data-agent-name')).toBe('Copilot');
    expect(viewport.attributes('data-welcome-hint')).toBe(
      'Copilot 正在准备开场建议',
    );

    const composer = wrapper.get('[data-testid="composer-probe"]');
    expect(composer.attributes('data-disabled')).toBe('true');
    expect(composer.attributes('data-send-disabled')).toBe('true');
    expect(composer.attributes('data-attach-disabled')).toBe('true');
    await composer.trigger('click');
    expect(wrapper.emitted('send')).toBeUndefined();
  });
});
