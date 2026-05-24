<script setup>

import { computed, onMounted, onUnmounted, ref } from 'vue'

import { adminApi } from '@/api/admin.js'



const tab = ref('members')



function onAdminTab(ev) {

  const t = ev?.detail

  if (t) tab.value = t

}



const err = ref('')

const me = ref(null)

const members = ref([])

const tgUsers = ref([])

const tgSummary = ref({})

const tgFilter = ref('pending')

const notifyPrefs = ref([])

const newsQ = ref('')

const newsItems = ref([])

const diaryItems = ref([])

const pestLinks = ref([])

const aiCrop = ref('토마토')

const aiSymptoms = ref('')

const aiImageB64 = ref('')

const aiResult = ref('')

const aiBusy = ref(false)



const selectedMember = ref(null)

const memberEdit = ref({ display_name: '', role: 'member', active: true })



const diaryForm = ref({

  diary_date: new Date().toISOString().slice(0, 10),

  title: '',

  body: '',

  crop: '',

  weather_note: '',

})



const memberForm = ref({ email: '', display_name: '', role: 'member' })

const tgForm = ref({ chat_id: '', display_name: '', enabled: true, notes: '' })



const isAdmin = computed(() => !!me.value?.is_admin)

const loginBlocked = computed(() => !!me.value?.login_disabled)



const tgFilterLabel = {

  pending: '신청 대기',

  approved: '승인',

  rejected: '거절',

  all: '전체',

}



function statusLabel(st) {

  const m = { pending: '대기', approved: '승인', rejected: '거절' }

  return m[st] || st || '—'

}



function fmtDt(v) {

  if (!v) return '—'

  return String(v).replace('T', ' ').slice(0, 19)

}



async function loadMembers() {

  members.value = (await adminApi.members()).items || []

}



async function loadTelegram() {

  const res = await adminApi.telegramUsers(tgFilter.value)

  tgUsers.value = res.items || []

  tgSummary.value = res.summary || {}

}



async function loadAll() {

  err.value = ''

  try {

    me.value = await adminApi.me()

    if (loginBlocked.value) {

      err.value = me.value?.message || '로그인이 차단되었습니다.'

      return

    }

    if (!isAdmin.value) {

      err.value = '관리자(role=admin)만 회원·텔레그램 사용자를 조회·변경할 수 있습니다.'

      return

    }

    await loadMembers()

    await loadTelegram()

    notifyPrefs.value = (await adminApi.notifyPrefs()).items || []

    await loadNews()

    diaryItems.value = (await adminApi.farmDiary()).items || []

    const pf = await adminApi.pestForecast()

    pestLinks.value = pf.links || []

  } catch (e) {

    err.value = e.message || String(e)

  }

}



async function loadNews() {

  newsItems.value = (await adminApi.news(newsQ.value)).items || []

}



async function addMember() {

  await adminApi.saveMember(memberForm.value)

  memberForm.value = { email: '', display_name: '', role: 'member' }

  await loadMembers()

}



async function addTg() {

  await adminApi.saveTelegramUser(tgForm.value)

  tgForm.value = { chat_id: '', display_name: '', enabled: true, notes: '' }

  await loadTelegram()

}



function selectMember(m) {

  selectedMember.value = m

  memberEdit.value = {

    display_name: m.display_name || '',

    role: m.role || 'member',

    active: !!m.active,

  }

}



async function saveMemberEdit() {

  const m = selectedMember.value

  if (!m?.id) return

  await adminApi.updateMember({

    id: m.id,

    display_name: memberEdit.value.display_name,

    role: memberEdit.value.role,

    active: memberEdit.value.active,

  })

  await loadMembers()

  const updated = members.value.find((x) => x.id === m.id)

  if (updated) selectMember(updated)

}



async function toggleMemberActive(m) {

  await adminApi.updateMember({ id: m.id, active: !m.active })

  await loadMembers()

  if (selectedMember.value?.id === m.id) {

    const updated = members.value.find((x) => x.id === m.id)

    if (updated) selectMember(updated)

  }

}



async function setTgStatus(t, status) {

  await adminApi.updateTelegramUser({ id: t.id, status })

  await loadTelegram()

}



async function onTgFilterChange() {

  await loadTelegram()

}



async function saveDiary() {

  await adminApi.saveDiary(diaryForm.value)

  diaryForm.value = {

    diary_date: new Date().toISOString().slice(0, 10),

    title: '',

    body: '',

    crop: '',

    weather_note: '',

  }

  diaryItems.value = (await adminApi.farmDiary()).items || []

}



async function removeDiary(id) {

  if (!confirm('이 일지를 삭제할까요?')) return

  await adminApi.deleteDiary(id)

  diaryItems.value = (await adminApi.farmDiary()).items || []

}



function onImageFile(ev) {

  const f = ev.target.files?.[0]

  if (!f) return

  const rd = new FileReader()

  rd.onload = () => {

    aiImageB64.value = String(rd.result || '')

  }

  rd.readAsDataURL(f)

}



async function runAi() {

  aiBusy.value = true

  aiResult.value = ''

  err.value = ''

  try {

    const res = await adminApi.aiDiagnose({

      crop: aiCrop.value,

      symptoms: aiSymptoms.value,

      image_base64: aiImageB64.value || undefined,

    })

    aiResult.value = res.diagnosis || res.error || JSON.stringify(res)

  } catch (e) {

    err.value = e.message || String(e)

  } finally {

    aiBusy.value = false

  }

}



onMounted(() => {

  loadAll()

  window.addEventListener('cf-admin-tab', onAdminTab)

})

onUnmounted(() => window.removeEventListener('cf-admin-tab', onAdminTab))

</script>



<template>

  <div class="cf-admin">

    <header class="cf-admin-hd">

      <h1 class="cf-sec-title">CronusFarm 관리</h1>

      <p v-if="me?.authenticated" class="cf-admin-me">

        로그인: {{ me.member?.email || me.email }}

        <span class="cf-admin-role">({{ me.member?.role || 'member' }})</span>

        <span v-if="isAdmin" class="ok"> · 관리자</span>

      </p>

      <p v-else-if="loginBlocked" class="cf-admin-me cf-admin-me--warn">

        {{ me?.message || '로그인이 차단되었습니다. 관리자에게 문의하세요.' }}

      </p>

      <p v-else class="cf-admin-me cf-admin-me--warn">

        OAuth 미연동 — nginx Google 로그인 적용 후 이메일이 표시됩니다.

      </p>

    </header>



    <nav class="cf-admin-tabs" aria-label="관리 메뉴">

      <button type="button" :class="{ on: tab === 'members' }" @click="tab = 'members'">회원·텔레그램</button>

      <button type="button" :class="{ on: tab === 'news' }" @click="tab = 'news'">영농 뉴스</button>

      <button type="button" :class="{ on: tab === 'ai' }" @click="tab = 'ai'">AI 작물 진단</button>

      <button type="button" :class="{ on: tab === 'diary' }" @click="tab = 'diary'">영농일지</button>

    </nav>



    <p v-if="err" class="err">{{ err }}</p>



    <section v-show="tab === 'members' && isAdmin" class="cf-settings-shell cf-settings-shell--wide">

      <h2 class="cf-admin-sub">Google 로그인 회원 (전체)</h2>

      <p class="cf-muted cf-admin-hint">

        Google OAuth로 접속한 사용자가 자동 등록됩니다. 비활성 시 farm-ui·관리 API 접근이 차단됩니다.

      </p>

      <div class="cf-admin-form">

        <input v-model="memberForm.email" type="email" placeholder="이메일(수동 추가)" />

        <input v-model="memberForm.display_name" type="text" placeholder="표시 이름" />

        <select v-model="memberForm.role">

          <option value="member">member</option>

          <option value="admin">admin</option>

        </select>

        <button type="button" class="btn btn-sm" @click="addMember">추가</button>

      </div>



      <div class="cf-admin-table-wrap">

        <table class="cf-admin-table">

          <thead>

            <tr>

              <th>이메일</th>

              <th>이름</th>

              <th>역할</th>

              <th>마지막 로그인</th>

              <th>텔레그램</th>

              <th>로그인</th>

              <th></th>

            </tr>

          </thead>

          <tbody>

            <tr

              v-for="m in members"

              :key="m.id"

              :class="{ sel: selectedMember?.id === m.id }"

              @click="selectMember(m)"

            >

              <td class="mono">{{ m.email }}</td>

              <td>{{ m.display_name || '—' }}</td>

              <td>{{ m.role }}</td>

              <td class="mono">{{ fmtDt(m.last_login_at) }}</td>

              <td>{{ m.tg_linked || 0 }}</td>

              <td>

                <span :class="m.active ? 'ok' : 'err'">{{ m.active ? '허용' : '차단' }}</span>

              </td>

              <td>

                <button

                  type="button"

                  class="btn btn-sm"

                  @click.stop="toggleMemberActive(m)"

                >

                  {{ m.active ? '차단' : '허용' }}

                </button>

              </td>

            </tr>

            <tr v-if="!members.length">

              <td colspan="7" class="cf-muted">등록된 회원이 없습니다.</td>

            </tr>

          </tbody>

        </table>

      </div>



      <div v-if="selectedMember" class="cf-admin-detail">

        <h3 class="cf-admin-sub">회원 상세 · #{{ selectedMember.id }}</h3>

        <dl class="cf-admin-dl">

          <dt>이메일</dt>

          <dd>{{ selectedMember.email }}</dd>

          <dt>Google sub</dt>

          <dd class="mono">{{ selectedMember.google_sub || '—' }}</dd>

          <dt>가입</dt>

          <dd>{{ fmtDt(selectedMember.created_at) }}</dd>

          <dt>수정</dt>

          <dd>{{ fmtDt(selectedMember.updated_at) }}</dd>

          <dt>알림 설정 수</dt>

          <dd>{{ selectedMember.notify_count ?? 0 }}</dd>

        </dl>

        <div class="cf-admin-form">

          <input v-model="memberEdit.display_name" type="text" placeholder="표시 이름" />

          <select v-model="memberEdit.role">

            <option value="member">member</option>

            <option value="admin">admin</option>

          </select>

          <label class="cf-admin-check">

            <input v-model="memberEdit.active" type="checkbox" />

            로그인 허용

          </label>

          <button type="button" class="btn btn-sm" @click="saveMemberEdit">저장</button>

        </div>

      </div>



      <h2 class="cf-admin-sub">텔레그램 알림 신청</h2>

      <p class="cf-muted cf-admin-hint">

        봇에 /start 를 보낸 사용자가 pending 으로 등록됩니다. 승인 시 알림(enabled)이 켜집니다.

        <span v-if="Object.keys(tgSummary).length">

          — 대기 {{ tgSummary.pending || 0 }} · 승인 {{ tgSummary.approved || 0 }} · 거절

          {{ tgSummary.rejected || 0 }}

        </span>

      </p>

      <div class="cf-admin-form">

        <select v-model="tgFilter" @change="onTgFilterChange">

          <option value="pending">신청 대기</option>

          <option value="approved">승인</option>

          <option value="rejected">거절</option>

          <option value="all">전체</option>

        </select>

        <input v-model="tgForm.chat_id" placeholder="chat_id (수동)" />

        <input v-model="tgForm.display_name" placeholder="이름" />

        <button type="button" class="btn btn-sm" @click="addTg">수동 등록</button>

      </div>



      <div class="cf-admin-table-wrap">

        <table class="cf-admin-table">

          <thead>

            <tr>

              <th>chat_id</th>

              <th>표시명</th>

              <th>@username</th>

              <th>상태</th>

              <th>신청일</th>

              <th>연동 회원</th>

              <th>알림</th>

              <th>처리</th>

            </tr>

          </thead>

          <tbody>

            <tr v-for="t in tgUsers" :key="t.id">

              <td class="mono">{{ t.chat_id }}</td>

              <td>{{ t.display_name || '—' }}</td>

              <td>{{ t.telegram_username ? '@' + t.telegram_username.replace(/^@/, '') : '—' }}</td>

              <td>

                <span

                  :class="{

                    ok: t.status === 'approved',

                    err: t.status === 'rejected',

                    warn: t.status === 'pending',

                  }"

                >

                  {{ statusLabel(t.status) }}

                </span>

              </td>

              <td class="mono">{{ fmtDt(t.applied_at || t.created_at) }}</td>

              <td>{{ t.member_email || '—' }}</td>

              <td>{{ t.enabled ? 'ON' : 'OFF' }}</td>

              <td class="cf-admin-actions">

                <template v-if="t.status === 'pending'">

                  <button type="button" class="btn btn-sm" @click="setTgStatus(t, 'approved')">승인</button>

                  <button type="button" class="btn btn-sm btn-danger" @click="setTgStatus(t, 'rejected')">

                    거절

                  </button>

                </template>

                <template v-else-if="t.status === 'rejected'">

                  <button type="button" class="btn btn-sm" @click="setTgStatus(t, 'approved')">재승인</button>

                </template>

                <template v-else>

                  <button type="button" class="btn btn-sm btn-danger" @click="setTgStatus(t, 'rejected')">

                    거절

                  </button>

                </template>

              </td>

            </tr>

            <tr v-if="!tgUsers.length">

              <td colspan="8" class="cf-muted">

                {{ tgFilterLabel[tgFilter] || tgFilter }} 목록이 비어 있습니다.

              </td>

            </tr>

          </tbody>

        </table>

      </div>



      <h2 class="cf-admin-sub">정보 수신 관리</h2>

      <ul class="cf-admin-list">

        <li v-for="n in notifyPrefs" :key="n.id">

          chat {{ n.telegram_chat_id || '—' }} · MQTT끊김 {{ n.mqtt_offline ? 'Y' : 'N' }}

          · 뉴스 {{ n.daily_news ? 'Y' : 'N' }} · 기상 {{ n.weather_brief ? 'Y' : 'N' }}

        </li>

        <li v-if="!notifyPrefs.length" class="cf-muted">수신 설정이 없습니다.</li>

      </ul>

    </section>



    <section v-show="tab === 'news' && isAdmin" class="cf-settings-shell cf-settings-shell--wide">

      <h2 class="cf-admin-sub">영농 뉴스</h2>

      <div class="cf-admin-form">

        <input v-model="newsQ" type="search" placeholder="검색어" @keyup.enter="loadNews" />

        <button type="button" class="btn btn-sm" @click="loadNews">검색</button>

      </div>

      <article v-for="n in newsItems" :key="n.id" class="cf-admin-news">

        <h3>{{ n.title }}</h3>

        <p>{{ n.summary }}</p>

        <a v-if="n.url" :href="n.url" target="_blank" rel="noopener">원문</a>

      </article>

    </section>



    <section v-show="tab === 'ai' && isAdmin" class="cf-settings-shell cf-settings-shell--wide">

      <h2 class="cf-admin-sub">AI 작물 진단</h2>

      <p class="cf-muted">

        사진·증상 설명을 Ollama로 분석합니다. 비전은 Pi에 llava 등 설치 후

        CRONUSFARM_OLLAMA_VISION_MODEL 설정이 필요합니다.

      </p>

      <div class="cf-admin-form cf-admin-form--col">

        <input v-model="aiCrop" placeholder="작물명" />

        <textarea v-model="aiSymptoms" rows="4" placeholder="증상·관찰 내용" />

        <input type="file" accept="image/*" @change="onImageFile" />

        <button type="button" class="btn" :disabled="aiBusy" @click="runAi">

          {{ aiBusy ? '진단 중…' : '진단 실행' }}

        </button>

      </div>

      <pre v-if="aiResult" class="cf-admin-ai-out">{{ aiResult }}</pre>

      <h3 class="cf-admin-sub">병해충 예찰·예보</h3>

      <ul class="cf-admin-list">

        <li v-for="(l, i) in pestLinks" :key="i">

          <a :href="l.url" target="_blank" rel="noopener">{{ l.label }}</a>

        </li>

      </ul>

    </section>



    <section v-show="tab === 'diary' && isAdmin" class="cf-settings-shell cf-settings-shell--wide">

      <h2 class="cf-admin-sub">영농일지 작성</h2>

      <div class="cf-admin-form cf-admin-form--col">

        <input v-model="diaryForm.diary_date" type="date" />

        <input v-model="diaryForm.title" placeholder="제목" />

        <input v-model="diaryForm.crop" placeholder="작물" />

        <input v-model="diaryForm.weather_note" placeholder="날씨 메모" />

        <textarea v-model="diaryForm.body" rows="6" placeholder="오늘 한 일" />

        <button type="button" class="btn" @click="saveDiary">저장</button>

      </div>

      <ul class="cf-admin-list cf-admin-diary">

        <li v-for="d in diaryItems" :key="d.id">

          <strong>{{ d.diary_date }}</strong> {{ d.title }}

          <p>{{ d.body }}</p>

          <button type="button" class="btn btn-sm btn-danger" @click="removeDiary(d.id)">삭제</button>

        </li>

      </ul>

    </section>

  </div>

</template>


