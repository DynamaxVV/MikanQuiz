<script setup lang="ts">
import { useRouter } from 'vue-router';
import BrandHeader from '@/components/BrandHeader.vue';
import mascotArtwork from '@/assets/mascot-study-with-bg.png';
import heroTitle from '../../../../miniprogram/images/hero-title-hanzipen.png';

const router = useRouter();
function beginQuiz(): void {
  void router.push('/levels');
}
</script>

<template>
  <main class="home-page">
    <div class="content">
      <BrandHeader :show-brand="false" show-feedback feedback-source="home" />
      <section class="hero" aria-labelledby="home-title">
        <div class="hero-main">
          <div class="hero-copy">
            <h1 id="home-title" class="sr-only">来和砂糖橘一起学嵌字吧</h1>
            <p class="eyebrow hero-eyebrow">砂糖橘的秘密小课堂</p>
            <img
              class="hero-title"
              :src="heroTitle"
              width="1800"
              height="260"
              alt="来和砂糖橘一起学嵌字吧"
              decoding="async"
            />
            <p class="subtitle">观察图片，选择最合适的中文字体~</p>
          </div>
          <div class="action-stack">
            <button class="action-card primary-card" type="button" @click="beginQuiz">
              <span><strong>开始识字挑战</strong><small>选择适合你的题目难度</small></span>
              <span aria-hidden="true">→</span>
            </button>
            <RouterLink class="action-card reference-card" to="/font-reference">
              <span><strong>嵌字小本本</strong><small>一点点点点也许嵌字会用上的教程</small></span>
              <span aria-hidden="true">→</span>
            </RouterLink>
            <aside class="recruit" aria-label="汉化工房九九组招募">
              <p class="recruit-intro">
                <strong>汉化工房九九组</strong><span> · </span>我们是(主打)萌系轻百合的汉化组
              </p>
              <p class="recruit-groups">
                <span>加入我们：826788824</span>
                <span>一起闲聊：554843287</span>
              </p>
            </aside>
          </div>
        </div>
        <div class="hero-artwork">
          <img
            class="mascot-artwork"
            :src="mascotArtwork"
            width="1322"
            height="1076"
            alt="砂糖橘陪伴猫耳女孩一起学习嵌字"
            decoding="async"
          />
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.home-page { min-height: 100vh; background: var(--color-bg); }
.content { width: min(1280px, calc(100% - clamp(48px, 8vw, 128px))); margin: 0 auto; }
.hero { display: grid; min-height: calc(100vh - 72px); grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: center; gap: clamp(32px, 4vw, 64px); padding: 40px 0 64px; }
.hero-main { min-width: 0; max-width: 620px; }
.hero-copy { --hero-text-inset: 2.1%; min-width: 0; }
.hero-eyebrow { margin-left: var(--hero-text-inset); }
.hero-title { display: block; width: min(100%, 620px); height: auto; margin-top: 12px; }
.subtitle { max-width: 520px; margin: 24px 0 0; padding-left: var(--hero-text-inset); color: var(--color-text-muted); font-size: 18px; line-height: 1.7; text-align: left; }
.action-stack { display: grid; gap: 16px; margin-top: 32px; }
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
.recruit { display: flex; height: calc(14px * 1.65 + 18px); flex-direction: column; justify-content: center; margin: 0; color: var(--color-text-muted); text-align: center; }
.recruit p { margin: 0; line-height: 20px; white-space: nowrap; }
.recruit-intro { font-size: 12px; }
.recruit-intro strong { color: var(--color-action); font-size: 15px; font-weight: 750; }
.recruit-groups { display: flex; justify-content: center; gap: 24px; font-size: 12px; font-weight: 400; }
.hero-artwork { min-width: 0; }
.mascot-artwork { display: block; width: 100%; height: auto; filter: drop-shadow(0 18px 32px rgba(116, 72, 20, .10)); transform: rotate(-1deg); }
@media (max-width: 1023px) { .hero { min-height: auto; grid-template-columns: 1fr; gap: 48px; } .hero-main { width: min(100%, 680px); max-width: none; } .hero-artwork { width: min(100%, 680px); } }
@media (min-width: 1024px) { .hero-artwork { transform: translateY(24px); } }
@media (max-width: 767px) { .content { width: min(100% - 32px, 1280px); } .hero { gap: 12px; padding: 8px 0 24px; } .hero-main { display: contents; } .hero-copy { grid-row: 1; } .hero-title { width: 100%; margin-top: 8px; } .subtitle { margin-top: 12px; font-size: 16px; } .hero-artwork { grid-row: 2; width: min(92%, 460px); margin: 0 auto; } .action-stack { grid-row: 3; gap: 10px; margin-top: 0; } .action-card { min-height: 96px; padding: 18px 20px; } .action-card strong { font-size: 20px; } .action-card small { margin-top: 5px; font-size: 13px; } .recruit { height: calc(14px * 1.65 + 10px); } .recruit p { line-height: 16px; } .recruit-intro { font-size: 11px; } .recruit-intro strong { font-size: 12px; } .recruit-groups { gap: 16px; font-size: 11px; } .mascot-artwork { transform: rotate(-.7deg); } }
@media (max-width: 359px) { .recruit-intro { font-size: 9px; } .recruit-intro strong { font-size: 11px; } .recruit-groups { gap: 12px; } }
@media (prefers-reduced-motion: reduce) { .action-card:hover, .action-card:active { transform: none; } }
</style>
