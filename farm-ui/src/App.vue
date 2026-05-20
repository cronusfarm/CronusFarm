<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const menuOpen = ref(false)

const monitorOrigin = () => (typeof location !== 'undefined' ? location.origin : '')

const settingsItems = [
  { id: 'sec-beds', label: '채널별 제어' },
  { id: 'sec-audit', label: '제어 감사' },
  { id: 'sec-sched-24h', label: '채널별 스케줄(24H)' },
  { id: 'sec-sched-edit', label: '스케줄 편집' },
  { id: 'sec-control', label: '관제' },
]

const monitorItems = [
  'A Bed',
  'B Bed',
  'C Bed',
  'D Bed',
  'Farm 환경',
  '센서 Data',
  'Arduino (R4)',
  'System (Pi)',
  'AI 작물 관측',
]

function closeMenu() {
  menuOpen.value = false
}

function scrollToSection(id) {
  closeMenu()
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onKey(e) {
  if (e.key === 'Escape') closeMenu()
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="cf-app">
    <header class="cf-mhdr">
      <button
        type="button"
        class="cf-mhdr-burger"
        :aria-expanded="menuOpen"
        aria-label="메뉴 열기"
        @click="menuOpen = !menuOpen"
      >
        <span /><span /><span />
      </button>
      <h1 class="cf-mhdr-title">CronusFarm 설정</h1>
    </header>

    <Teleport to="body">
      <div v-if="menuOpen" class="cf-drawer-back" @click="closeMenu" />
      <nav class="cf-drawer" :class="{ open: menuOpen }" aria-label="설정 메뉴">
        <div class="cf-drawer-hd">메뉴</div>
        <p class="cf-drawer-sec-title">CronusFarm 설정</p>
        <button
          v-for="item in settingsItems"
          :key="item.id"
          type="button"
          class="cf-drawer-item"
          @click="scrollToSection(item.id)"
        >
          {{ item.label }}
        </button>
        <p class="cf-drawer-sec-title">CronusFarm 모니터</p>
        <a
          v-for="label in monitorItems"
          :key="label"
          :href="`${monitorOrigin()}/ui/#ui-tab_monitor`"
          class="cf-drawer-item cf-drawer-ext"
          @click="closeMenu"
        >
          {{ label }}
        </a>
      </nav>
    </Teleport>

    <main class="cf-app-main cf-app-main--single">
      <RouterView />
    </main>
  </div>
</template>
