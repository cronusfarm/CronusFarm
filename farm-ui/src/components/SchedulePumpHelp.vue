<script setup>
/** Pump A1~B2 주기+시간대 편집 형식 설명(다이어그램) */
</script>

<template>
  <div class="cf-pump-help">
    <h4 class="cf-pump-help-title">Pump A1·A2·B2 편집 형식 (주기 + 시간대 제한)</h4>
    <p class="cf-pump-help-p">
      DB에는 <strong>구간마다 규칙 1줄</strong>입니다. 편집 화면의 「② 주기」에서
      <strong>시간대 제한</strong>을 켜면 아래와 같이 저장됩니다.
    </p>

    <div class="cf-pump-diagram">
      <div class="cf-pump-diagram-cap">하루 24시간 띠 (Pump A1 예)</div>
      <pre class="cf-pump-ascii" aria-label="Pump A1 하루 스케줄 다이어그램">00:00        09:00              17:00        24:00
|-------------|-------------------|-------------|
  야간 구간        주간 구간(낮)         야간 구간
  5분 ON          10분 ON              5분 ON
  55분 OFF        50분 OFF             55분 OFF
  (반복)          (반복)               (반복)

편집기에 보이는 3행 ≈ 위 3구간을 각각 한 줄로 저장
  ① 주간 09:00~17:00  ON 10분 / OFF 50분  [시간대 제한 ✓]
  ② 야간 00:00~09:00  ON 5분  / OFF 55분  [시간대 제한 ✓]
  ③ 야간 17:00~24:00  ON 5분  / OFF 55분  [시간대 제한 ✓]</pre>
    </div>

    <div class="cf-pump-diagram">
      <div class="cf-pump-diagram-cap">한 구간 안에서의 반복 (예: 주간 10/50)</div>
      <pre class="cf-pump-ascii" aria-label="10분 ON 50분 OFF 주기">|--ON 10분--|----OFF 50분----|--ON 10분--|----OFF 50분----|→
   ↑_______________ 60분(1시간) 주기 _______________↑
   자정(00:00) 기준으로 60분 패턴이 하루 종일 반복
   (09:00~17:00 안에서만 이 주기가 돌아감)</pre>
    </div>

    <ul class="cf-pump-help-list">
      <li><strong>시간대 제한 OFF</strong> → 하루 종일 같은 ON/OFF 길이만 반복 (Pump C/D)</li>
      <li><strong>시간대 제한 ON</strong> → 켜짐~꺼짐 시각 <em>안에서만</em> 주기 반복 (Pump A/B)</li>
      <li>저장 후 <strong>저장 (DB+MQTT)</strong> → Arduino에 즉시 반영</li>
    </ul>
  </div>
</template>
