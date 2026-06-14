<script setup>

import { computed, onMounted, onUnmounted, ref } from 'vue'

import { useRoute, useRouter } from 'vue-router'



const route = useRoute()

const router = useRouter()

const menuOpen = ref(false)



const isAdmin = computed(() => route.name === 'admin')

const pageTitle = computed(() =>

  isAdmin.value ? 'CronusFarm 관리' : 'CronusFarm 설정',

)



const monitorOrigin = () => (typeof location !== 'undefined' ? location.origin : '')



const settingsItems = [

  { id: 'sec-beds', label: '채널별 제어' },

  { id: 'sec-sched-24h', label: '채널별 스케줄(24H)' },

  { id: 'sec-sched-edit', label: '채널별 스케줄 편집' },

  { id: 'sec-sched-defaults', label: '기본 스케줄표' },

  { id: 'sec-control', label: '관제' },

  { id: 'sec-audit', label: '제어 감사' },

]



const adminItems = [

  { tab: 'members', label: '회원·텔레그램·수신' },

  { tab: 'news', label: '영농 뉴스' },

  { tab: 'ai', label: 'AI 작물 진단' },

  { tab: 'diary', label: '영농일지' },

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



function goAdminTab(tab) {

  closeMenu()

  if (route.name !== 'admin') {

    router.push({ name: 'admin' }).then(() => {

      window.dispatchEvent(new CustomEvent('cf-admin-tab', { detail: tab }))

    })

  } else {

    window.dispatchEvent(new CustomEvent('cf-admin-tab', { detail: tab }))

  }

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

      <h1 class="cf-mhdr-title">{{ pageTitle }}</h1>

      <nav class="cf-mhdr-nav">

        <RouterLink to="/" class="cf-mhdr-link" active-class="on" @click="closeMenu">

          설정

        </RouterLink>

        <RouterLink to="/admin" class="cf-mhdr-link" active-class="on" @click="closeMenu">

          관리

        </RouterLink>

      </nav>

    </header>



    <Teleport to="body">

      <div v-if="menuOpen" class="cf-drawer-back" @click="closeMenu" />

      <nav class="cf-drawer" :class="{ open: menuOpen }" aria-label="메뉴">

        <div class="cf-drawer-hd">메뉴</div>

        <RouterLink to="/" class="cf-drawer-item cf-drawer-route" @click="closeMenu">

          CronusFarm 설정

        </RouterLink>

        <RouterLink to="/admin" class="cf-drawer-item cf-drawer-route" @click="closeMenu">

          CronusFarm 관리

        </RouterLink>



        <template v-if="!isAdmin">

          <p class="cf-drawer-sec-title">설정 화면</p>

          <button

            v-for="item in settingsItems"

            :key="item.id"

            type="button"

            class="cf-drawer-item"

            @click="scrollToSection(item.id)"

          >

            {{ item.label }}

          </button>

        </template>

        <template v-else>

          <p class="cf-drawer-sec-title">관리</p>

          <button

            v-for="item in adminItems"

            :key="item.tab"

            type="button"

            class="cf-drawer-item"

            @click="goAdminTab(item.tab)"

          >

            {{ item.label }}

          </button>

        </template>



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


