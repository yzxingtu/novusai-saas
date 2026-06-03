<script lang="ts" setup>
import { adminAnnouncementApi } from '#/api/admin/announcement';
import AnnouncementManagementPage from '#/components/business/announcement/AnnouncementManagementPage.vue';

defineOptions({ name: 'AdminSystemAnnouncements' });
</script>

<template>
  <AnnouncementManagementPage
    :api="adminAnnouncementApi"
    i18n-prefix="admin.system.announcements"
  />
</template>
