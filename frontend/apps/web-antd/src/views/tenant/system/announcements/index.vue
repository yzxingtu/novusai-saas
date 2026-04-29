<script lang="ts" setup>
import { tenantAnnouncementApi } from '#/api/tenant/announcement';
import AnnouncementManagementPage from '#/components/business/announcement/AnnouncementManagementPage.vue';

defineOptions({ name: 'TenantSystemAnnouncements' });
</script>

<template>
  <AnnouncementManagementPage
    :api="tenantAnnouncementApi"
    i18n-prefix="tenant.system.announcements"
  />
</template>
