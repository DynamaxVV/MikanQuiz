<script setup lang="ts">
import { useRouter } from 'vue-router';
import BrandHeader from '@/components/BrandHeader.vue';
import heroTitle from '../../../../miniprogram/images/hero-title-hanzipen.png';

const router = useRouter();
function beginQuiz(): void {
  void router.push('/levels');
}
</script>

<template>
  <main class="home-page">
    <div class="content">
      <BrandHeader :show-brand="false" />
      <section class="hero" aria-labelledby="home-title">
        <div class="hero-copy">
          <div class="hero-sun" aria-hidden="true"></div>
          <h1 id="home-title" class="sr-only">砂糖的秘密小课堂</h1>
          <p class="eyebrow hero-eyebrow">砂糖的秘密小课堂</p>
          <img class="hero-title" :src="heroTitle" alt="汉字盆" />
          <p class="subtitle">  观察图片，选择最合适的中文字体~</p>
        </div>
        <div class="action-stack">
          <button class="action-card primary-card" type="button" @click="beginQuiz">
            <span><strong>开始识字挑战</strong><small>选择适合你的题目难度</small></span>
            <span aria-hidden="true">→</span>
          </button>
          <RouterLink class="action-card reference-card" to="/font-reference">
            <span><strong>字体对照表</strong><small>查看常用字形对照图片</small></span>
            <span aria-hidden="true">→</span>
          </RouterLink>
          <p class="hint">提交后会自动评分，并告诉你每一题的思路。</p>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.home-page { min-height: 100vh; background: var(--color-bg); }
.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }
.hero { display: grid; min-height: calc(100vh - 72px); grid-template-columns: minmax(0, 1.38fr) minmax(360px, 1fr); align-items: center; gap: clamp(40px, 7vw, 112px); padding: 40px 0 64px; }
.hero-copy { --hero-text-inset: 2.1%; position: relative; z-index: 0; max-width: 650px; transform: translateY(-28px); }.hero-sun { position: absolute; z-index: 0; top: clamp(-78px, -6vw, -42px); right: clamp(-92px, -8vw, -44px); width: clamp(150px, 20vw, 260px); aspect-ratio: 1; border-radius: 50%; background: #fff0d2; pointer-events: none; }.hero-title, .subtitle, .hero-eyebrow { position: relative; z-index: 1; }.hero-eyebrow { margin-left: var(--hero-text-inset); }.hero-title { display: block; width: min(100%, 620px); margin-top: 12px; }.subtitle { max-width: 520px; margin: 24px 0 0; padding-left: var(--hero-text-inset); color: var(--color-text-muted); font-size: 18px; line-height: 1.7; text-align: left; }
.action-stack { position: relative; z-index: 1; display: grid; gap: 16px; align-content: center; }
.action-card { display: flex; min-height: 126px; align-items: center; justify-content: space-between; gap: 20px; padding: 26px 28px; border: 1px solid var(--color-border); border-radius: 24px; box-shadow: var(--shadow-card); text-align: left; transition: transform 160ms ease-out, box-shadow 160ms ease-out; }
.action-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-card-hover); }
.action-card:active { transform: scale(.98); }
.action-card strong { display: block; font-size: 22px; letter-spacing: -.015em; }
.action-card small { display: block; margin-top: 8px; font-size: 15px; line-height: 1.5; }
.action-card > span:last-child { font-size: 32px; font-weight: 300; }
.primary-card { border-color: var(--color-action); color: #fff; background: var(--color-action); box-shadow: 0 18px 36px rgba(169, 79, 31, .24); }
.primary-card small { color: #fff; }
.reference-card { color: var(--color-text); background: var(--color-surface); }
.reference-card small { color: var(--color-text-muted); }
.hint { margin: 18px auto 0; color: var(--color-text-muted); font-size: 14px; line-height: 1.65; text-align: center; }
@media (max-width: 1023px) { .hero { grid-template-columns: 1fr; gap: 48px; } .hero-copy { transform: none; } .action-stack { max-width: 680px; } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); } .hero { min-height: auto; padding-top: 32px; } .hero-title { width: 100%; } .subtitle { font-size: 16px; } .action-card { min-height: 108px; padding: 22px; } }
@media (prefers-reduced-motion: reduce) { .action-card:hover, .action-card:active { transform: none; } }
</style>
