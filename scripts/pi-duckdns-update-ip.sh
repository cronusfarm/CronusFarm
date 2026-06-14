#!/usr/bin/env bash
# DuckDNS A 레코드를 현재 공인 IPv4로 갱신 (선택)
# 설정: /etc/cronusfarm/duckdns.env
#   DUCKDNS_DOMAIN=cronusfarm
#   DUCKDNS_TOKEN=<duckdns 토큰>
set -euo pipefail

ENV_FILE="${DUCKDNS_ENV:-/etc/cronusfarm/duckdns.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  exit 0
fi
# shellcheck disable=SC1090
source "$ENV_FILE"
DOMAIN="${DUCKDNS_DOMAIN:-cronusfarm}"
TOKEN="${DUCKDNS_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "skip: DUCKDNS_TOKEN 없음 ($ENV_FILE)" >&2
  exit 0
fi
IP="$(curl -4 -sS --max-time 10 "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=")"
echo "duckdns update: $IP"
if [[ "$IP" != "OK" ]]; then
  echo "WARN: DuckDNS 응답이 OK가 아님" >&2
  exit 1
fi
