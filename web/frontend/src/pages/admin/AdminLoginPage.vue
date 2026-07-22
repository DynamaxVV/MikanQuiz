<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api/client';

const route = useRoute();
const router = useRouter();
const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');
const target = computed(() => {
  const next = typeof route.query.next === 'string' ? route.query.next : '/admin/questions';
  return next.startsWith('/admin/') ? next : '/admin/questions';
});

async function login(): Promise<void> {
  error.value = '';
  if (!username.value.trim() || !password.value) { error.value = '请输入管理员账号和密码。'; return; }
  loading.value = true;
  try {
    await api.login(username.value.trim(), password.value);
    password.value = '';
    await router.replace(target.value);
  } catch (caught) { error.value = caught instanceof Error ? caught.message : '登录失败，请重试。'; }
  finally { loading.value = false; }
}
</script>

<template>
  <main class="login-page"><section class="login-card card" aria-labelledby="login-title"><RouterLink class="back" to="/">← 返回公开首页</RouterLink><p class="eyebrow">管理员入口</p><h1 id="login-title" class="page-title">登录题库管理</h1><p class="page-description">管理员账号由服务器运维维护；登录后可管理题库、策略与提交记录。</p><form @submit.prevent="login"><label>账号<input v-model="username" autocomplete="username" autofocus /></label><label>密码<input v-model="password" type="password" autocomplete="current-password" /></label><p v-if="error" class="status-error" role="alert">{{ error }}</p><button type="submit" :disabled="loading">{{ loading ? '正在登录…' : '登录管理端' }}</button></form></section></main>
</template>

<style scoped>
.login-page { display: grid; min-height: 100vh; padding: 24px; place-items: center; background: var(--color-bg); }.login-card { width: min(460px, 100%); padding: 34px; }.back { display: inline-block; margin-bottom: 36px; color: var(--color-action); font-size: 14px; font-weight: 700; }.login-card .page-description { margin-bottom: 26px; }.login-card form { display: grid; gap: 16px; }.login-card label { display: grid; gap: 8px; font-size: 14px; font-weight: 700; }.login-card input { min-height: 44px; border: 1px solid var(--color-border); border-radius: var(--radius-input); padding: 0 12px; color: var(--color-text); background: var(--color-surface-warm); }.login-card button { min-height: 46px; border: 0; border-radius: var(--radius-button); color: #fff; background: var(--color-action); font-weight: 700; }.login-card button:hover { background: var(--color-action-hover); }.login-card button:disabled { opacity: .6; }
</style>
