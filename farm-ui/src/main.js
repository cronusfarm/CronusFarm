import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { ensurePiClockPolling } from '@/composables/usePiClock'
import './assets/cronusfarm_shared.css'
import './styles/settings.css'

ensurePiClockPolling()
const app = createApp(App).use(router)
app.mount('#app')
