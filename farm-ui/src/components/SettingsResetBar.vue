<script setup>
import { onMounted, ref } from 'vue'
import { adminApi } from '@/api/admin.js'

const busy = ref('')
const msg = ref('')
const err = ref('')
const auth = ref(null)

async function loadAuth() {
  try {
    auth.value = await adminApi.authStatus(currentSiteHost())
  } catch {
    auth.value = null
  }
}

async function runReset(target, label, { upload = false } = {}) {
  if (busy.value) return
  const hint = upload
    ? '컴파일·업로드 포함 (수 분 소요)'
    : '펌웨어 재시작만 (업로드 없음, 약 10~30초)'
  if (!confirm(`${label} — 진행할까요?\n${hint}`)) return
  busy.value = target
  msg.value = ''
  err.value = ''
  try {
    const res = await adminApi.reset(target)
    if (res.ok) {
      msg.value = `${label} 완료`
      if (res.log_tail) msg.value += ` — ${res.log_tail.slice(-120)}`
    } else {
      err.value = res.error || res.log_tail || `${label} 실패 (code ${res.exit_code})`
    }
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    busy.value = ''
    if (target === 'ida') await loadAuth()
  }
}

const OAUTH_HOSTS = ['cronusfarm.duckdns.org']

function currentSiteHost() {
  if (typeof location === 'undefined') return ''
  return (location.hostname || '').toLowerCase()
}

const oauthAppliesHere = () => {
  const h = currentSiteHost()
  return OAUTH_HOSTS.some((d) => h === d || h.endsWith('.' + d))
}

const oauthSignInUrl = () => {
  if (typeof location === 'undefined') return '/oauth2/start'
  return `/oauth2/start?rd=${encodeURIComponent(location.href)}`
}

const loginLabel = () => {
  if (!oauthAppliesHere()) {
    const h = currentSiteHost() || '이 주소'
    return `Google 로그인: ${h} 는 OAuth 미적용(Tailscale·LAN) — duckdns.org 로 접속`
  }
  const s = auth.value?.google_login
  if (s === 'active') return 'Google 로그인 (duckdns.org)'
  if (s === 'configured_not_running') return 'Google: CLIENT 설정됨 — Pi에서 oauth2-proxy 재시작'
  return 'Google: Pi에 CLIENT 미설정'
}

const showLoginLink = () => oauthAppliesHere() && auth.value?.google_login === 'active'

onMounted(loadAuth)
</script>

<template>
  <div class="cf-reset-bar">
    <div class="cf-reset-line">
      <span class="cf-reset-title">소프트웨어 리셋</span>
      <button
        type="button"
        class="btn btn-sm"
        :class="{ 'is-busy': busy === 'ida' }"
        :disabled="!!busy"
        @click="runReset('ida', 'ida 서비스(NR·nginx·브리지)')"
      >
        {{ busy === 'ida' ? '…' : 'ida' }}
      </button>
      <span class="cf-reset-sep">R4</span>
      <button
        type="button"
        class="btn btn-sm"
        :class="{ 'is-busy': busy === 'r4-soft' }"
        :disabled="!!busy"
        @click="runReset('r4-soft', 'R4 리셋')"
      >
        {{ busy === 'r4-soft' ? '…' : '리셋' }}
      </button>
      <button
        type="button"
        class="btn btn-sm btn-prim"
        :class="{ 'is-busy': busy === 'r4' }"
        :disabled="!!busy"
        @click="runReset('r4', 'R4 업로드', { upload: true })"
      >
        {{ busy === 'r4' ? '…' : '업로드' }}
      </button>
      <span class="cf-reset-sep">R3</span>
      <button
        type="button"
        class="btn btn-sm"
        :class="{ 'is-busy': busy === 'r3-soft' }"
        :disabled="!!busy"
        @click="runReset('r3-soft', 'R3 패널 리셋')"
      >
        {{ busy === 'r3-soft' ? '…' : '리셋' }}
      </button>
      <button
        type="button"
        class="btn btn-sm btn-prim"
        :class="{ 'is-busy': busy === 'r3' }"
        :disabled="!!busy"
        @click="runReset('r3', 'R3 패널 업로드', { upload: true })"
      >
        {{ busy === 'r3' ? '…' : '업로드' }}
      </button>
      <span v-if="auth" class="cf-reset-auth-inline">
        {{ loginLabel() }}
        <a v-if="showLoginLink()" :href="oauthSignInUrl()" class="cf-reset-oauth-link">로그인</a>
        <a
          v-else-if="!oauthAppliesHere()"
          href="https://cronusfarm.duckdns.org/farm/ui/"
          class="cf-reset-oauth-link"
          target="_blank"
          rel="noopener"
        >duckdns 열기</a>
      </span>
    </div>
    <span v-if="msg" class="ok">{{ msg }}</span>
    <span v-if="err" class="err">{{ err }}</span>
  </div>
</template>
