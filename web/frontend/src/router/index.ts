import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', component: () => import('@/pages/HomePage.vue'), meta: { title: '砂糖橘的秘密小课堂' } },
    { path: '/levels', component: () => import('@/pages/LevelsPage.vue'), meta: { title: '选择难度' } },
    { path: '/quiz/:attempt', component: () => import('@/pages/QuizPage.vue'), meta: { title: '字形练习' } },
    { path: '/result/:attempt', component: () => import('@/pages/ResultPage.vue'), meta: { title: '答题结果' } },
    { path: '/font-reference', component: () => import('@/pages/FontReferencePage.vue'), meta: { title: '嵌字笔记' } },
    { path: '/admin/login', component: () => import('@/pages/admin/AdminLoginPage.vue'), meta: { title: '管理员登录' } },
    { path: '/admin/questions', component: () => import('@/pages/admin/AdminQuestionsPage.vue'), meta: { title: '题库', admin: true } },
    { path: '/admin/questions/new', component: () => import('@/pages/admin/AdminQuestionFormPage.vue'), meta: { title: '新增题目', admin: true } },
    { path: '/admin/questions/:id', component: () => import('@/pages/admin/AdminQuestionDetailPage.vue'), meta: { title: '题目详情', admin: true } },
    { path: '/admin/questions/:id/edit', component: () => import('@/pages/admin/AdminQuestionFormPage.vue'), meta: { title: '编辑题目', admin: true } },
    { path: '/admin/strategy', component: () => import('@/pages/admin/AdminStrategyPage.vue'), meta: { title: '出题策略', admin: true } },
    { path: '/admin/font-presets', component: () => import('@/pages/admin/AdminFontPresetsPage.vue'), meta: { title: '字体快捷项', admin: true } },
    { path: '/admin/font-references', component: () => import('@/pages/admin/AdminFontReferencesPage.vue'), meta: { title: '嵌字笔记管理', admin: true } },
    { path: '/admin/submissions', component: () => import('@/pages/admin/AdminSubmissionsPage.vue'), meta: { title: '提交记录', admin: true } },
    { path: '/:pathMatch(.*)*', component: () => import('@/pages/NotFoundPage.vue'), meta: { title: '页面未找到' } },
  ],
});

router.beforeEach((to) => { document.title = (to.meta.title as string) ?? '砂糖橘的秘密小课堂'; });

export default router;
