<script setup lang="ts">
defineProps<{ message: string; title?: string }>();
const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <section class="error-panel" role="alert">
    <strong>{{ title ?? '暂时无法加载' }}</strong>
    <p>{{ message }}</p>
    <button type="button" @click="emit('retry')">重试</button>
  </section>
</template>

<style scoped>
.error-panel { padding: 20px; border: 1px solid #ecc3be; border-radius: 16px; color: #7d2f2a; background: #fff0ee; }
.error-panel p { margin: 8px 0 14px; line-height: 1.55; }
button { min-height: 38px; border: 1px solid #b5483f; border-radius: 10px; padding: 0 13px; color: #7d2f2a; background: #fff; font-weight: 650; }
</style>
