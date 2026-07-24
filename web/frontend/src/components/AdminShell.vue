<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElDrawer } from 'element-plus';
import 'element-plus/dist/index.css';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api/client';
import type { AdminSession } from '@/types';

const route = useRoute();
const router = useRouter();
const session = ref<AdminSession | null>(null);
const checking = ref(true);
const drawerOpen = ref(false);
const navItems = [
  { label: '题库', to: '/admin/questions', exact: true },
  { label: '新增题目', to: '/admin/questions/new' },
  { label: '出题策略', to: '/admin/strategy' },
  { label: '字体快捷项', to: '/admin/font-presets' },
  { label: '字形教程', to: '/admin/font-references' },
];
const activePath = computed(() => route.path);

async function checkSession(): Promise<void> {
  checking.value = true;
  try { session.value = await api.getAdminSession(); }
  catch { await router.replace(`/admin/login?next=${encodeURIComponent(route.fullPath)}`); }
  finally { checking.value = false; }
}

async function logout(): Promise<void> {
  try { await api.logout(); } finally { await router.push('/admin/login'); }
}

function closeDrawer(): void { drawerOpen.value = false; }
onMounted(() => { void checkSession(); });
</script>

<template>
  <main class="admin-frame">
    <button class="mobile-menu" type="button" aria-label="打开管理导航" @click="drawerOpen = true">☰ 菜单</button>
    <aside class="sidebar desktop-sidebar">
      <div class="sidebar-inner"><RouterLink class="admin-brand" to="/">砂糖的秘密小课堂</RouterLink><nav aria-label="管理导航"><RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item" :class="{ active: item.exact ? activePath === item.to : activePath.startsWith(item.to) }">{{ item.label }}</RouterLink></nav><div class="sidebar-footer"><span v-if="session" class="logout">{{ session.username }}</span><RouterLink class="logout" to="/">返回答题首页</RouterLink><button type="button" @click="logout">退出登录</button></div></div>
    </aside>
    <el-drawer v-model="drawerOpen" direction="ltr" size="280px" :with-header="false" class="admin-drawer">
      <div class="drawer-inner"><RouterLink class="admin-brand" to="/" @click="closeDrawer">砂糖的秘密小课堂</RouterLink><nav aria-label="管理导航"><RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item" :class="{ active: item.exact ? activePath === item.to : activePath.startsWith(item.to) }" @click="closeDrawer">{{ item.label }}</RouterLink></nav><RouterLink class="logout" to="/" @click="closeDrawer">返回答题首页</RouterLink><button class="logout" type="button" @click="logout">退出登录</button></div>
    </el-drawer>
    <section class="admin-main" :aria-busy="checking"><div v-if="checking" class="admin-loading">正在验证管理员会话…</div><slot v-else-if="session" :session="session"></slot></section>
  </main>
</template>

<style scoped>
.admin-frame { min-height: 100vh; background: var(--color-bg); }.sidebar { position: fixed; z-index: 2; inset: 0 auto 0 0; width: 232px; border-right: 1px solid var(--color-border); background: rgba(255, 250, 242, .78); backdrop-filter: blur(18px) saturate(150%); }.sidebar-inner, .drawer-inner { display: flex; height: 100%; flex-direction: column; padding: 24px 14px; }.admin-brand { display: flex; align-items: center; min-height: 32px; padding: 0 10px; color: var(--color-accent); font-size: 15px; font-weight: 750; }nav { display: grid; gap: 5px; margin-top: 42px; }.nav-item { min-height: 44px; display: flex; align-items: center; border-left: 3px solid transparent; border-radius: 0 10px 10px 0; padding: 0 12px; color: var(--color-text-muted); font-size: 15px; font-weight: 650; }.nav-item:hover { color: var(--color-action); background: rgba(255, 240, 216, .65); }.nav-item.active { border-left-color: var(--color-action); color: var(--color-text); background: var(--color-surface-accent); }.sidebar-footer { display: grid; gap: 10px; margin-top: auto; padding: 12px 10px 0; color: var(--color-text-muted); font-size: 13px; }.sidebar-footer button, .logout { min-height: 40px; border: 0; border-radius: 10px; color: var(--color-text-muted); background: transparent; text-align: left; }.sidebar-footer button:hover, .logout:hover { color: var(--color-danger); background: #fff0ee; }.admin-main { min-width: 0; min-height: 100vh; margin-left: 232px; }.admin-loading { display: grid; min-height: 100vh; place-items: center; color: var(--color-text-muted); }.mobile-menu { display: none; }
.sidebar-footer { padding-left: 0; padding-right: 0; }.sidebar-footer > *, .drawer-inner > .logout { padding: 0 10px; }
@media (max-width: 1023px) { .desktop-sidebar { display: none; }.admin-main { margin-left: 0; padding-top: 58px; }.mobile-menu { position: fixed; z-index: 4; top: 10px; left: 14px; display: inline-flex; min-height: 38px; align-items: center; border: 1px solid var(--color-border); border-radius: 10px; padding: 0 12px; color: var(--color-text); background: rgba(255, 250, 242, .9); font-weight: 700; box-shadow: 0 4px 14px rgba(116, 72, 20, .08); } }
@media (prefers-reduced-transparency: reduce) { .sidebar { background: #fffaf2; backdrop-filter: none; } }
</style>

<style>
.admin-drawer .el-drawer__body { padding: 0; background: #fffaf2; }
</style>
