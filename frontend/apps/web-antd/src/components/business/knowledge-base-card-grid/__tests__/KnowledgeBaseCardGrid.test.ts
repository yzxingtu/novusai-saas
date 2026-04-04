// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import KnowledgeBaseCardGrid from '../KnowledgeBaseCardGrid.vue';

/* eslint-disable vue/one-component-per-file */

vi.mock('ant-design-vue', () => ({
  Badge: defineComponent({
    name: 'BadgeStub',
    template: '<div><slot /></div>',
  }),
  Button: defineComponent({
    name: 'ButtonStub',
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  }),
  Dropdown: defineComponent({
    name: 'DropdownStub',
    template: '<div><slot /><slot name="overlay" /></div>',
  }),
  Empty: defineComponent({
    name: 'EmptyStub',
    template: '<div><slot /></div>',
  }),
  Menu: defineComponent({
    name: 'MenuStub',
    template: '<div><slot /></div>',
  }),
  MenuItem: defineComponent({
    name: 'MenuItemStub',
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  }),
  Pagination: defineComponent({
    name: 'PaginationStub',
    template: '<div />',
  }),
  Spin: defineComponent({
    name: 'SpinStub',
    template: '<div><slot /></div>',
  }),
  Tag: defineComponent({
    name: 'TagStub',
    template: '<span><slot /></span>',
  }),
  Tooltip: defineComponent({
    name: 'TooltipStub',
    template: '<div><slot /></div>',
  }),
}));

describe('knowledgeBaseCardGrid', () => {
  it('emits select and menuAction events from rendered cards', async () => {
    const wrapper = mount(KnowledgeBaseCardGrid, {
      props: {
        emptyDescription: 'empty',
        loading: false,
        value: [
          {
            id: 1,
            name: 'KB One',
            description: 'Desc',
            embeddingModelName: 'text-embedding-3-large',
            statusColor: 'success',
            statusText: 'Active',
            scopeColor: 'purple',
            scopeText: 'Global',
            documentCount: 3,
            totalChunks: 12,
            totalSizeText: '1 MB',
            createdAtText: 'today',
            createdAtTitle: '2026-01-01',
            secondaryAction: {
              key: 'edit',
              label: 'Edit',
              icon: 'lucide:pencil',
            },
            menuActions: [
              { key: 'detail', label: 'Detail', icon: 'lucide:eye' },
              {
                key: 'delete',
                label: 'Delete',
                icon: 'lucide:trash-2',
                danger: true,
              },
            ],
          },
        ],
      },
      global: {
        stubs: {
          Dropdown: {
            template: '<div><slot /><slot name="overlay" /></div>',
          },
          Empty: {
            template: '<div><slot /></div>',
          },
          IconifyIcon: {
            template: '<i />',
          },
          Menu: {
            template: '<div><slot /></div>',
          },
          MenuItem: {
            props: ['class'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          Pagination: {
            template: '<div />',
          },
          Spin: {
            template: '<div><slot /></div>',
          },
          Tooltip: {
            template: '<div><slot /></div>',
          },
        },
      },
    });

    await wrapper.find('h4').trigger('click');
    expect(wrapper.emitted('select')).toEqual([[1]]);

    const editButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Edit'));
    await editButton?.trigger('click');
    expect(wrapper.emitted('menuAction')).toEqual([['edit', 1]]);
  });
});
