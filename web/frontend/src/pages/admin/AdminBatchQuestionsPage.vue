<script setup lang="ts">
import AdminShell from '@/components/AdminShell.vue';
import BatchWorkspace from '@/components/BatchWorkspace.vue';
</script>

<template>
  <AdminShell focus-mode v-slot="{ session }"><BatchWorkspace :username="session.username" /></AdminShell>
</template>
