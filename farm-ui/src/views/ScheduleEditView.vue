<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ScheduleEditor from '@/components/ScheduleEditor.vue'

const route = useRoute()
const channel = ref('led_a1')
const editorRef = ref(null)

function applyRouteChannel() {
  const q = route.query.channel
  if (typeof q === 'string' && q.trim()) {
    channel.value = q.trim()
  }
}

onMounted(async () => {
  applyRouteChannel()
  await nextTick()
  editorRef.value?.loadSch?.()
})

watch(
  () => route.query.channel,
  async () => {
    applyRouteChannel()
    await nextTick()
    editorRef.value?.loadSch?.()
  },
)
</script>

<template>
  <div class="cf-settings-shell">
    <ScheduleEditor ref="editorRef" v-model:channel="channel" />
  </div>
</template>
