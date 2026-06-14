import { ref, watch } from 'vue'

const STORAGE_KEY = 'cfDeviceId'
const deviceId = ref('cronusfarm-01')

try {
  const s = localStorage.getItem(STORAGE_KEY)
  if (s && s.trim()) deviceId.value = s.trim()
} catch {
  /* ignore */
}

watch(deviceId, (v) => {
  try {
    localStorage.setItem(STORAGE_KEY, (v || '').trim())
  } catch {
    /* ignore */
  }
})

export function useDevice() {
  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, (deviceId.value || '').trim())
    } catch {
      /* ignore */
    }
  }

  return { deviceId, persist }
}
