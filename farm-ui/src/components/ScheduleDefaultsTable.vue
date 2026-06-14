<script setup>
import { SCHEDULE_DEFAULTS_BEDS } from '@/constants/scheduleDefaultsDisplay'
</script>

<template>
  <section class="cf-def-sch cf-def-sch--plain">
    <p class="cf-def-sch-sub">
      Bed 순 · DB 시드·펌웨어 builtin 동일. 수동 60분 후 AUTO. 패널 먹통 시 리셋 없이 푸시
      2회(0.45초 안)로 I2C·브라우즈 재동기화.
    </p>
    <div class="cf-def-sch-scroll">
      <table class="cf-def-sch-tbl">
        <thead>
          <tr>
            <th>Bed</th>
            <th>채널</th>
            <th>종류</th>
            <th>내용</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="bed in SCHEDULE_DEFAULTS_BEDS" :key="bed.bed">
            <tr v-for="(row, ri) in bed.rows" :key="bed.bed + row.label">
              <td v-if="ri === 0" class="cf-def-grp" :rowspan="bed.rows.length">{{ bed.bed }}</td>
              <td class="cf-def-ch">{{ row.label }}</td>
              <td class="cf-def-kind">{{ row.rule }}</td>
              <td class="cf-def-detail">{{ row.detail }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>
