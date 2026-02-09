<script lang="ts" setup>
defineOptions({ name: 'TenantAIConfig' });

import { Page } from '@vben/common-ui';

import { Card, Tabs, TabPane } from 'ant-design-vue';

import { $t } from '#/locales';

import ApiKeys from '../api-keys/index.vue';
import Models from '../models/index.vue';
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <Card :body-style="{ padding: '0' }">
      <Tabs default-active-key="keys" class="px-4">
        <TabPane key="keys" :tab="$t('tenant.ai.apiKey.title')">
          <ApiKeys />
        </TabPane>
        <TabPane key="models" :tab="$t('tenant.ai.model.title')">
          <Models />
        </TabPane>
      </Tabs>
    </Card>
  </Page>
</template>
