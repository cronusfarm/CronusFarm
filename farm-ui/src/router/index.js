import { createRouter, createWebHashHistory } from 'vue-router'
import SettingsAllView from '@/views/SettingsAllView.vue'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'settings', component: SettingsAllView, meta: { title: '설정' } },
    { path: '/beds', redirect: '/' },
    { path: '/schedule-24h', redirect: '/' },
    { path: '/schedule-edit', redirect: '/' },
    { path: '/control', redirect: '/' },
    { path: '/tools', redirect: '/' },
  ],
})

export default router
