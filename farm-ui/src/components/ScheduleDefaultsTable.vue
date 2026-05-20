<script setup>
import { SCHEDULE_DEFAULTS_BEDS } from '@/constants/scheduleDefaultsDisplay'
</script>

<template>
  <div class="cf-def-sch">
    <h3 class="cf-def-sch-title">기본 스케줄표</h3>
    <p class="cf-def-sch-sub">Bed 순 · DB 시드·펌웨어 builtin 동일</p>
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
  </div>
</template>
