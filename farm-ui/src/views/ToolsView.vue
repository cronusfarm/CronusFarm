<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ScheduleEditor from '@/components/ScheduleEditor.vue'
import ControlHub from '@/components/ControlHub.vue'

const route = useRoute()
const channel = ref('led_a1')
const editorRef = ref(null)

function applyRouteChannel() {
  const q = route.query.channel
  if (typeof q === 'string' && q.trim()) {
    channel.value = q.trim()
    editorRef.value?.loadSch?.()
  }
}

onMounted(async () => {
  applyRouteChannel()
  await nextTick()
  editorRef.value?.loadSch?.()
})

watch(
  () => route.query.channel,
  () => applyRouteChannel(),
)
</script>

<template>
  <div class="cf-settings-shell cf-tools-page">
    <ScheduleEditor ref="editorRef" v-model:channel="channel" />
    <hr class="cf-tools-hr" />
    <ControlHub />
  </div>
</template>
