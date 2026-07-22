<template>
  <main class="not-found">
    <section class="card">
      <p class="eyebrow">找不到页面</p>
      <h1 class="page-title">这页可能已经换了位置</h1>
      <p>请回到首页重新开始。</p>
      <RouterLink to="/">返回首页</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.not-found { display: grid; min-height: 100vh; padding: 24px; place-items: center; background: var(--color-bg); }
.card { width: min(520px, 100%); padding: 36px; }
p { color: var(--color-text-muted); line-height: 1.65; }
a { display: inline-block; margin-top: 12px; color: var(--color-action); font-weight: 700; }
</style>
