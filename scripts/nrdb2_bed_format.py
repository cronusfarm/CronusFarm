# -*- coding: utf-8 -*-
"""NRDB2 Bed 카드 ui-template `format` 문자열 생성 (A/B/C/D 공통)."""

from __future__ import annotations

import re


def extract_channels_inner(fmt: str) -> str | None:
    m = re.search(r"channels:\s*\[([\s\S]*?)\n\s*\]", fmt)
    if not m:
        return None
    return m.group(1).strip()


def reorder_channels_inner(inner: str) -> str:
    items = re.findall(r"\{[^\n]+\}", inner)
    if len(items) < 2:
        return inner

    def sort_key(line: str) -> tuple[int, str]:
        tm = re.search(r"t: '([^']+)'", line)
        t = tm.group(1) if tm else ""
        if t.startswith("led_"):
            return (0, t)
        if t.startswith("pump_"):
            return (1, t)
        if t.startswith("fan_"):
            return (2, t)
        return (3, t)

    items_sorted = sorted(items, key=sort_key)
    indent = "        "
    return "\n" + ",\n".join(f"{indent}{it.strip()}" for it in items_sorted) + "\n      "


# /ui 모니터 타일과 동일 계열 SVG (짧은 버전, 백틱 JS 문자열용 — 백틱 없음)
_SVG_LED = (
    "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" width=\"28\" height=\"28\">"
    "<circle cx=\"12\" cy=\"12\" r=\"4\" fill=\"#FFD54F\"/>"
    "<g stroke=\"#FFD54F\" stroke-width=\"2\" stroke-linecap=\"round\">"
    "<path d=\"M12 2v3\"/><path d=\"M12 19v3\"/><path d=\"M2 12h3\"/><path d=\"M19 12h3\"/>"
    "<path d=\"M4.2 4.2l2.1 2.1\"/><path d=\"M17.7 17.7l2.1 2.1\"/>"
    "<path d=\"M19.8 4.2l-2.1 2.1\"/><path d=\"M6.3 17.7l-2.1 2.1\"/></g></svg>"
)
_SVG_PUMP = (
    "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" width=\"28\" height=\"28\">"
    "<path fill=\"#4FC3F7\" d=\"M7 3h10v4h-1v10a4 4 0 0 1-8 0V7H7V3z\"/>"
    "<path fill=\"#BBDEFB\" d=\"M9 7h6v10a3 3 0 0 1-6 0V7z\" opacity=\".55\"/>"
    "<path fill=\"#90CAF9\" d=\"M6 8h2v2H6c-1.1 0-2 .9-2 2v6h2v2H2v-8a4 4 0 0 1 4-4z\"/></svg>"
)
_SVG_FAN = (
    "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" width=\"28\" height=\"28\">"
    "<circle cx=\"12\" cy=\"12\" r=\"9\" fill=\"none\" stroke=\"#43A047\" stroke-width=\"2\"/>"
    "<path fill=\"#43A047\" d=\"M12 5.5c1.2 0 2 1.6 1 2.6-.6.7-1.5 1-1.3 1.6.2.5 1 .4 1.7.4 1.4 0 2.1 1.8.8 2.6-.6.4-1.4.4-1.6.8-.2.4.4.9 1 1.4 1 .9.2 2.3-1 2.3-.9 0-1.7-.7-2.1-1.2.1.6.2 1.4 0 2-.5 1.2-2.3 1.1-2.6-.2-.2-.7.1-1.4.4-2-.5.4-1.1 1-2 1-1.2 0-2-1.6-1-2.6.5-.5 1.2-.9 1-1.4-.2-.5-1-.4-1.6-.8-1.3-.8-.6-2.6.8-2.6.7 0 1.4.1 1.6-.4.2-.4-.5-.8-1-1.4C10 7.1 10.8 5.5 12 5.5z\" opacity=\".9\"/></svg>"
)


def build_nrdb2_bed_format(channels_inner: str) -> str:
    """채널 배열 내부 텍스트만 넣어 전체 ui-template format 생성."""
    ch = reorder_channels_inner(channels_inner)
    bt = "`"
    # JS template literal: return `...svg...`
    ret_led = f"      if (t.startsWith('led_')) return {bt}{_SVG_LED}{bt}\n"
    ret_pump = f"      if (t.startsWith('pump_')) return {bt}{_SVG_PUMP}{bt}\n"
    ret_fan = f"      if (t.startsWith('fan_')) return {bt}{_SVG_FAN}{bt}\n"
    return f"""<template>
  <div class="cf2-bed">
    <div class="cf2-bed-hd">{{{{ title }}}}</div>
    <div v-for="ch in channels" :key="ch.t" class="cf2-row">
      <div class="cf2-left">
        <div class="cf2-ic" v-html="iconSvg(ch)"></div>
        <div class="cf2-chinfo">
          <div class="cf2-name">{{{{ ch.label }}}} <span class="cf2-pin">{{{{ ch.pin }}}}</span></div>
        </div>
      </div>
      <div class="ctrl-col">
        <div class="ctrl-wrap">
          <button type="button"
            class="ctrlBtn"
            :class="[ch.state === 'ON' ? 'is-on' : 'is-off', {{ holding: ch.holding }}]"
            @mousedown.prevent="startHold(ch, $event)"
            @mouseup="endHold(ch)"
            @mouseleave="endHold(ch)"
            @touchstart.prevent="startHold(ch, $event)"
            @touchend="endHold(ch)"
            @click="handleClick(ch)">
            <span class="modeInBtn" :class="ch.mode === '자동' ? 'mi-auto' : 'mi-manual'">{{{{ ch.mode }}}}</span>
            <span class="mainState" :class="ch.state.toLowerCase()">{{{{ ch.state }}}}</span>
          </button>
          <div class="holdBarWrap" :class="{{ visible: ch.holding }}">
            <div class="holdBar" :style="{{ width: ch.holdPct + '%' }}"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {{
  data () {{
    return {{
      title: "",
      channels: [
{ch}      ]
    }}
  }},
  methods: {{
    iconSvg (ch) {{
      const t = (ch && ch.t) ? String(ch.t) : ''
{ret_led}{ret_pump}{ret_fan}      return ''
    }},
    startHold (ch, e) {{
      if (e && e.preventDefault) e.preventDefault()
      ch.holdFired = false
      ch.holding = true
      ch.holdPct = 0
      const HOLD_MS = 700
      const t0 = Date.now()
      ch._holdI = setInterval(() => {{
        ch.holdPct = Math.min((Date.now() - t0) / HOLD_MS * 100, 100)
      }}, 30)
      ch._holdT = setTimeout(() => {{
        ch.holdFired = true
        if (ch.mode === '자동') {{
          ch.mode = '수동'
          this.send({{ topic: ch.at, payload: 0 }})
        }} else {{
          ch.mode = '자동'
          this.send({{ topic: ch.at, payload: 1 }})
        }}
        this.endHold(ch)
      }}, HOLD_MS)
    }},
    endHold (ch) {{
      if (ch._holdT) {{ clearTimeout(ch._holdT); ch._holdT = null }}
      if (ch._holdI) {{ clearInterval(ch._holdI); ch._holdI = null }}
      ch.holding = false
      ch.holdPct = 0
    }},
    handleClick (ch) {{
      if (ch.holdFired) {{ ch.holdFired = false; return }}
      if (ch.mode !== '수동') return
      ch.state = ch.state === 'ON' ? 'OFF' : 'ON'
      const v = ch.state === 'ON' ? 1 : 0
      this.send({{ topic: ch.t, payload: v }})
    }}
  }}
}}
</script>

<style scoped>
.cf2-bed {{ display: flex; flex-direction: column; gap: 4px; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.cf2-bed-hd {{ display:none; }}
.cf2-row {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 12px;
  background: linear-gradient(165deg, rgba(255,255,255,.08), rgba(255,255,255,.02));
  border: 1px solid rgba(255,255,255,.1);
}}
.cf2-left {{ display: flex; align-items: center; gap: 8px; min-width: 0; }}
.cf2-ic {{ width: 32px; height: 32px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }}
.cf2-ic :deep(svg) {{ display: block; max-width: 100%; height: auto; }}
.cf2-chinfo {{ display: flex; flex-direction: column; justify-content: center; min-width: 0; flex: 1; }}
.cf2-name {{ font-size: 14px; font-weight: 900; color: #e6edf7; letter-spacing: .01em; line-height: 1.2; }}
.cf2-pin {{ color: #9db0cc; font-weight: 700; font-size: 10px; margin-left: 4px; }}
.ctrl-col {{ display: flex; flex-direction: column; align-items: flex-end; justify-content: center; }}
.ctrl-wrap {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-shrink: 0;
}}
.modeInBtn {{
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  line-height: 1;
  margin-bottom: 2px;
  opacity: 0.92;
}}
.modeInBtn.mi-auto {{ color: rgba(200, 255, 220, 0.95); }}
.modeInBtn.mi-manual {{ color: rgba(255, 236, 180, 0.95); }}
.ctrlBtn {{
  position: relative;
  width: 118px;
  min-height: 46px;
  border-radius: 12px;
  border: 2px solid rgba(255,255,255,.14);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s, box-shadow 0.2s, border-color 0.2s;
  outline: none;
  -webkit-tap-highlight-color: transparent;
  padding: 5px 6px 6px;
}}
.ctrlBtn.is-on {{
  border-color: rgba(52,199,89,.65);
  background: linear-gradient(165deg, rgba(34,120,60,.95), rgba(20,70,40,.88));
  box-shadow: 0 6px 16px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.12);
}}
.ctrlBtn.is-off {{
  border-color: rgba(255,80,60,.55);
  background: linear-gradient(165deg, rgba(120,40,34,.95), rgba(70,24,20,.88));
  box-shadow: 0 6px 16px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.08);
}}
.ctrlBtn:hover {{
  box-shadow: 0 8px 20px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.14);
}}
.ctrlBtn:active {{ transform: translateY(1px) scale(0.99); }}
.ctrlBtn.holding {{ box-shadow: 0 0 0 3px rgba(79,140,255,.45); }}
.mainState {{
  font-size: 20px;
  font-weight: 900;
  letter-spacing: 0.04em;
  color: #ffffff !important;
  text-shadow: 0 2px 10px rgba(0,0,0,.55), 0 0 1px rgba(0,0,0,.8);
}}
.holdBarWrap {{
  width: 118px;
  height: 3px;
  background: rgba(255,255,255,.18);
  border-radius: 99px;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.1s;
}}
.holdBarWrap.visible {{ opacity: 1; }}
.holdBar {{ height: 100%; width: 0%; background: #7db7ff; border-radius: 99px; }}
</style>
"""
