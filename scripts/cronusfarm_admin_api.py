# -*- coding: utf-8 -*-
"""CronusFarm 관리 API (SQLite 브리지용)."""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]

_ADMIN_SQL = (Path(__file__).resolve().parent / "sql" / "cronusfarm_admin_v2.sql").read_text(
    encoding="utf-8"
)
_ADMIN_SQL_V3 = (Path(__file__).resolve().parent / "sql" / "cronusfarm_admin_v3.sql").read_text(
    encoding="utf-8"
)


def _ensure_admin_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(_ADMIN_SQL)
    for stmt in _ADMIN_SQL_V3.split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    conn.commit()


def oauth_email_from_headers(headers: Any) -> str | None:
    return _oauth_identity_from_headers(headers).get("email")


def _oauth_identity_from_headers(headers: Any) -> dict[str, str | None]:
    """nginx oauth2-proxy / Google 헤더."""
    email = None
    for key in ("X-Auth-Request-Email", "X-Forwarded-Email", "X-User-Email"):
        v = (headers.get(key) or "").strip()
        if v and "@" in v:
            email = v.lower()
            break
    google_sub = None
    for key in ("X-Auth-Request-User", "X-Forwarded-User", "X-User-Id"):
        v = (headers.get(key) or "").strip()
        if v:
            google_sub = v
            break
    display_name = None
    for key in ("X-Auth-Request-Preferred-Username", "X-Forwarded-Preferred-Username"):
        v = (headers.get(key) or "").strip()
        if v:
            display_name = v
            break
    return {"email": email, "google_sub": google_sub, "display_name": display_name}


def _admin_bootstrap_emails() -> set[str]:
    raw = os.environ.get("CRONUSFARM_ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip() and "@" in e}


def _require_admin(
    conn: sqlite3.Connection, headers: Any
) -> tuple[bool, dict | None, tuple[int, dict | str] | None]:
    """관리 API: active=1 이고 role=admin (부트스트랩 이메일 포함)."""
    ident = _oauth_identity_from_headers(headers)
    email = ident.get("email")
    if not email:
        return False, None, (401, {"ok": False, "error": "로그인 필요(Google OAuth)"})
    cur = conn.cursor()
    cur.execute("SELECT * FROM cf_member WHERE email=?", (email,))
    row = cur.fetchone()
    if not row:
        return False, None, (403, {"ok": False, "error": "등록된 회원 없음"})
    member = _row_to_dict(row)
    if not int(member.get("active") or 0):
        return False, member, (403, {"ok": False, "error": "로그인 비활성(관리자 차단)"})
    boot = _admin_bootstrap_emails()
    if member.get("role") == "admin" or email in boot:
        return True, member, None
    cur.execute("SELECT COUNT(*) FROM cf_member WHERE role='admin' AND active=1")
    if int(cur.fetchone()[0] or 0) == 0:
        cur.execute(
            "UPDATE cf_member SET role='admin', updated_at=datetime('now') WHERE id=?",
            (member["id"],),
        )
        conn.commit()
        cur.execute("SELECT * FROM cf_member WHERE id=?", (member["id"],))
        return True, _row_to_dict(cur.fetchone()), None
    return False, member, (403, {"ok": False, "error": "관리자 권한 필요(role=admin)"})


def _touch_member_login(
    conn: sqlite3.Connection,
    email: str,
    google_sub: str | None = None,
    display_name: str | None = None,
) -> dict:
    cur = conn.cursor()
    boot = _admin_bootstrap_emails()
    cur.execute("SELECT COUNT(*) FROM cf_member WHERE role='admin' AND active=1")
    no_admin = int(cur.fetchone()[0] or 0) == 0
    role = "admin" if email in boot or no_admin else "member"
    cur.execute("SELECT * FROM cf_member WHERE email=?", (email,))
    row = cur.fetchone()
    if row:
        cur.execute(
            """UPDATE cf_member SET
               google_sub=COALESCE(?, google_sub),
               display_name=COALESCE(NULLIF(?, ''), display_name),
               role=CASE WHEN ? THEN 'admin' ELSE role END,
               last_login_at=datetime('now'),
               updated_at=datetime('now')
               WHERE email=?""",
            (google_sub, display_name or "", 1 if no_admin else 0, email),
        )
    else:
        cur.execute(
            """INSERT INTO cf_member (email, display_name, google_sub, role, active, last_login_at)
            VALUES (?,?,?,?,1,datetime('now'))""",
            (email, display_name or email.split("@")[0], google_sub, role),
        )
    conn.commit()
    cur.execute("SELECT * FROM cf_member WHERE email=?", (email,))
    return _row_to_dict(cur.fetchone())


def register_telegram_application(
    conn: sqlite3.Connection,
    chat_id: str,
    display_name: str = "",
    telegram_username: str = "",
) -> dict:
    """텔레그램 /start 등 — 신청(pending) 등록."""
    _ensure_admin_tables(conn)
    cid = str(chat_id or "").strip()
    if not cid:
        return {"ok": False, "error": "chat_id required"}
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO cf_telegram_user
        (chat_id, display_name, telegram_username, status, applied_at, enabled, notes)
        VALUES (?,?,?,?,datetime('now'),0,'봇 /start 자동 신청')
        ON CONFLICT(chat_id) DO UPDATE SET
          display_name=COALESCE(NULLIF(excluded.display_name,''), cf_telegram_user.display_name),
          telegram_username=COALESCE(NULLIF(excluded.telegram_username,''), cf_telegram_user.telegram_username),
          applied_at=CASE WHEN cf_telegram_user.status='pending'
            THEN datetime('now') ELSE cf_telegram_user.applied_at END,
          updated_at=datetime('now')""",
        (cid, display_name or "", telegram_username or "", "pending"),
    )
    conn.commit()
    cur.execute("SELECT * FROM cf_telegram_user WHERE chat_id=?", (cid,))
    return {"ok": True, "item": _row_to_dict(cur.fetchone())}

def _row_to_dict(row: sqlite3.Row | tuple | None) -> dict:
    if row is None:
        return {}
    if isinstance(row, sqlite3.Row):
        return {k: row[k] for k in row.keys()}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}  # type: ignore[union-attr]
    return {}


def handle_admin_get(
    conn: sqlite3.Connection,
    path: str,
    qs: dict[str, list[str]],
    headers: Any,
) -> tuple[int, dict | str]:
    _ensure_admin_tables(conn)
    cur = conn.cursor()

    if path == "/api/admin/me":
        ident = _oauth_identity_from_headers(headers)
        email = ident.get("email")
        if not email:
            return 200, {"authenticated": False, "email": None, "login_disabled": False}
        member = _touch_member_login(
            conn, email, ident.get("google_sub"), ident.get("display_name")
        )
        if not int(member.get("active") or 0):
            return 200, {
                "authenticated": False,
                "email": email,
                "login_disabled": True,
                "message": "관리자에 의해 로그인이 차단되었습니다.",
                "member": member,
            }
        is_admin = member.get("role") == "admin" or email in _admin_bootstrap_emails()
        return 200, {
            "authenticated": True,
            "email": email,
            "login_disabled": False,
            "is_admin": is_admin,
            "member": member,
        }

    if path == "/api/auth/verify":
        ident = _oauth_identity_from_headers(headers)
        email = ident.get("email")
        if not email:
            return 401, {"ok": False, "reason": "no_email"}
        cur.execute("SELECT active, role FROM cf_member WHERE email=?", (email,))
        row = cur.fetchone()
        if not row:
            return 403, {"ok": False, "reason": "not_registered"}
        if not int(row[0]):
            return 403, {"ok": False, "reason": "login_disabled"}
        return 200, {"ok": True, "email": email, "role": row[1]}

    if path == "/api/admin/members":
        ok, _admin, err = _require_admin(conn, headers)
        if not ok:
            return err  # type: ignore[return-value]
        cur.execute(
            """SELECT m.id, m.email, m.display_name, m.google_sub, m.role, m.active,
            m.created_at, m.updated_at, m.last_login_at,
            (SELECT COUNT(*) FROM cf_telegram_user t WHERE t.member_id = m.id) AS tg_linked,
            (SELECT COUNT(*) FROM cf_notify_pref n WHERE n.member_id = m.id) AS notify_count
            FROM cf_member m ORDER BY m.id DESC"""
        )
        return 200, {"items": [_row_to_dict(r) for r in cur.fetchall()]}

    if path == "/api/admin/telegram-users":
        ok, _admin, err = _require_admin(conn, headers)
        if not ok:
            return err  # type: ignore[return-value]
        status_f = ((qs.get("status") or [""])[0] or "").strip().lower()
        sql = """SELECT t.id, t.chat_id, t.display_name, t.telegram_username, t.member_id,
            t.status, t.enabled, t.notes, t.applied_at, t.created_at, t.updated_at,
            m.email AS member_email, m.display_name AS member_display_name
            FROM cf_telegram_user t
            LEFT JOIN cf_member m ON m.id = t.member_id
            WHERE 1=1"""
        args: list[Any] = []
        if status_f and status_f != "all":
            sql += " AND t.status=?"
            args.append(status_f)
        sql += " ORDER BY CASE t.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, t.id DESC"
        cur.execute(sql, args)
        items = [_row_to_dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT status, COUNT(*) AS c FROM cf_telegram_user GROUP BY status"
        )
        summary = {str(r[0]): int(r[1]) for r in cur.fetchall()}
        return 200, {"items": items, "summary": summary, "filter": status_f or "all"}

    if path == "/api/admin/notify-prefs":
        cur.execute(
            """SELECT n.*, m.email AS member_email
            FROM cf_notify_pref n
            LEFT JOIN cf_member m ON m.id = n.member_id
            ORDER BY n.id"""
        )
        return 200, {"items": [_row_to_dict(r) for r in cur.fetchall()]}

    if path == "/api/admin/news":
        q = ((qs.get("q") or [""])[0] or "").strip()
        limit = min(100, max(1, int((qs.get("limit") or ["30"])[0] or 30)))
        if q:
            like = f"%{q}%"
            cur.execute(
                """SELECT id, source, title, summary, url, published_at, tags, created_at
                FROM cf_news_clip
                WHERE title LIKE ? OR summary LIKE ? OR tags LIKE ?
                ORDER BY COALESCE(published_at, created_at) DESC LIMIT ?""",
                (like, like, like, limit),
            )
        else:
            cur.execute(
                """SELECT id, source, title, summary, url, published_at, tags, created_at
                FROM cf_news_clip ORDER BY COALESCE(published_at, created_at) DESC LIMIT ?""",
                (limit,),
            )
        items = [_row_to_dict(r) for r in cur.fetchall()]
        if not items:
            items = _news_fallback_briefing(conn)
        return 200, {"items": items, "query": q}

    if path == "/api/admin/farm-diary":
        limit = min(200, max(1, int((qs.get("limit") or ["50"])[0] or 50)))
        cur.execute(
            """SELECT id, member_id, author_email, diary_date, title, body, crop, weather_note,
            created_at, updated_at FROM cf_farm_diary
            ORDER BY diary_date DESC, id DESC LIMIT ?""",
            (limit,),
        )
        return 200, {"items": [_row_to_dict(r) for r in cur.fetchall()]}

    if path == "/api/admin/auth-status":
        site_host = ((qs.get("site_host") or [""])[0] or "").strip()
        return 200, _auth_status(site_host)

    if path == "/api/admin/pest-forecast":
        return 200, {
            "title": "전국 병해충 예찰·예보",
            "links": [
                {
                    "label": "농촌진흥청 병해충 예찰정보",
                    "url": "https://www.nongsaro.go.kr/portal/ps/psb/psbb/farmPestForecastList.ps?menuId=PS04101",
                },
                {
                    "label": "농식품부 농업재해·병해충",
                    "url": "https://www.mafra.go.kr",
                },
            ],
            "note": "상세 API 연동 전 안내 링크입니다. Pi KMA·MQTT 상태는 모니터 탭에서 확인하세요.",
        }

    return 404, "not found"


def _news_fallback_briefing(conn: sqlite3.Connection) -> list[dict]:
    """DB 뉴스 없을 때 KMA 스냅샷·설정으로 1건 브리핑."""
    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM settings_kv WHERE device_id=? AND key=? ORDER BY updated_at DESC LIMIT 1",
        ("cronusfarm-01", "kma_snapshot_json"),
    )
    row = cur.fetchone()
    summary = "저장된 뉴스 클립이 없습니다. 텔레그램 일일 뉴스·KMA 연동 후 자동 적재 예정입니다."
    if row and row[0]:
        try:
            k = json.loads(row[0])
            summary = (
                f"KMA 스냅샷: 기온 {k.get('kma_temp','—')}°C, 습도 {k.get('kma_humidity','—')}%, "
                f"강수형태 {k.get('kma_precip_type','—')}"
            )
        except json.JSONDecodeError:
            summary = str(row[0])[:400]
    return [
        {
            "id": 0,
            "source": "cronusfarm",
            "title": "영농 브리핑 (로컬)",
            "summary": summary,
            "url": "",
            "published_at": None,
            "tags": "briefing",
            "created_at": None,
        }
    ]


def handle_admin_post(
    conn: sqlite3.Connection,
    path: str,
    body: dict,
    headers: Any,
) -> tuple[int, dict | str]:
    _ensure_admin_tables(conn)
    cur = conn.cursor()
    email = oauth_email_from_headers(headers)

    if path == "/api/admin/members":
        ok, _, err = _require_admin(conn, headers)
        if not ok:
            return err  # type: ignore[return-value]
        em = str(body.get("email") or "").strip().lower()
        if not em:
            return 400, "email required"
        cur.execute(
            """INSERT INTO cf_member (email, display_name, role, active)
            VALUES (?,?,?,?)
            ON CONFLICT(email) DO UPDATE SET
              display_name=excluded.display_name, role=excluded.role,
              active=excluded.active, updated_at=datetime('now')""",
            (
                em,
                str(body.get("display_name") or em.split("@")[0]),
                str(body.get("role") or "member"),
                1 if body.get("active", True) else 0,
            ),
        )
        conn.commit()
        return 200, {"ok": True}

    if path == "/api/admin/telegram-users":
        ok, _, err = _require_admin(conn, headers)
        if not ok:
            return err  # type: ignore[return-value]
        cid = str(body.get("chat_id") or "").strip()
        if not cid:
            return 400, "chat_id required"
        st = str(body.get("status") or "approved").strip().lower()
        if st not in ("pending", "approved", "rejected"):
            st = "approved"
        en = 1 if body.get("enabled", st == "approved") else 0
        cur.execute(
            """INSERT INTO cf_telegram_user
            (chat_id, display_name, member_id, enabled, notes, status, applied_at, telegram_username)
            VALUES (?,?,?,?,?,?,datetime('now'),?)
            ON CONFLICT(chat_id) DO UPDATE SET
              display_name=excluded.display_name, member_id=excluded.member_id,
              enabled=excluded.enabled, notes=excluded.notes,
              status=excluded.status, telegram_username=COALESCE(excluded.telegram_username, telegram_username),
              updated_at=datetime('now')""",
            (
                cid,
                str(body.get("display_name") or ""),
                body.get("member_id"),
                en,
                str(body.get("notes") or ""),
                st,
                str(body.get("telegram_username") or ""),
            ),
        )
        conn.commit()
        return 200, {"ok": True}

    if path == "/api/admin/notify-prefs":
        cur.execute(
            """INSERT INTO cf_notify_pref
            (member_id, telegram_chat_id, mqtt_offline, daily_news, weather_brief, ai_alerts)
            VALUES (?,?,?,?,?,?)""",
            (
                body.get("member_id"),
                str(body.get("telegram_chat_id") or ""),
                1 if body.get("mqtt_offline", True) else 0,
                1 if body.get("daily_news", True) else 0,
                1 if body.get("weather_brief", True) else 0,
                1 if body.get("ai_alerts", False) else 0,
            ),
        )
        conn.commit()
        return 200, {"ok": True, "id": cur.lastrowid}

    if path == "/api/admin/farm-diary":
        if not str(body.get("body") or "").strip():
            return 400, "body required"
        cur.execute(
            """INSERT INTO cf_farm_diary
            (member_id, author_email, diary_date, title, body, crop, weather_note)
            VALUES (?,?,?,?,?,?,?)""",
            (
                body.get("member_id"),
                email or str(body.get("author_email") or ""),
                str(body.get("diary_date") or "")[:10] or _today_kst(),
                str(body.get("title") or ""),
                str(body.get("body") or ""),
                str(body.get("crop") or ""),
                str(body.get("weather_note") or ""),
            ),
        )
        conn.commit()
        return 200, {"ok": True, "id": cur.lastrowid}

    if path == "/api/admin/ai-diagnose":
        return _ai_diagnose(body)

    if path.startswith("/api/admin/reset/"):
        target = path.rsplit("/", 1)[-1].strip().lower()
        return _handle_reset(target)

    if path == "/api/admin/news/seed":
        title = str(body.get("title") or "테스트 뉴스")
        cur.execute(
            """INSERT INTO cf_news_clip (source, title, summary, url, published_at, tags)
            VALUES (?,?,?,?, datetime('now'), ?)""",
            (
                str(body.get("source") or "manual"),
                title,
                str(body.get("summary") or ""),
                str(body.get("url") or ""),
                str(body.get("tags") or ""),
            ),
        )
        conn.commit()
        return 200, {"ok": True, "id": cur.lastrowid}

    return 404, "not found"


def handle_admin_put(
    conn: sqlite3.Connection,
    path: str,
    body: dict,
    headers: Any | None = None,
) -> tuple[int, dict | str]:
    _ensure_admin_tables(conn)
    cur = conn.cursor()

    if path == "/api/admin/members":
        ok, _, err = _require_admin(conn, headers or {})
        if not ok:
            return err  # type: ignore[return-value]
        mid = int(body.get("id") or 0)
        if mid < 1:
            return 400, "id required"
        sets: list[str] = ["updated_at=datetime('now')"]
        args: list[Any] = []
        if "display_name" in body:
            sets.append("display_name=?")
            args.append(str(body.get("display_name") or ""))
        if "role" in body:
            sets.append("role=?")
            args.append(str(body.get("role") or "member"))
        if "active" in body:
            sets.append("active=?")
            args.append(1 if body.get("active") else 0)
        if len(sets) < 2:
            return 400, "nothing to update"
        args.append(mid)
        cur.execute(f"UPDATE cf_member SET {', '.join(sets)} WHERE id=?", args)
        conn.commit()
        return 200, {"ok": True}

    if path == "/api/admin/telegram-users":
        ok, _, err = _require_admin(conn, headers or {})
        if not ok:
            return err  # type: ignore[return-value]
        tid = int(body.get("id") or 0)
        if tid < 1:
            return 400, "id required"
        cur.execute("SELECT enabled, status FROM cf_telegram_user WHERE id=?", (tid,))
        old = cur.fetchone()
        if not old:
            return 404, "not found"
        old_en, old_st = int(old[0] or 0), str(old[1] or "pending")
        st = body.get("status")
        new_st = str(st).strip().lower() if st is not None else old_st
        if "enabled" in body:
            new_en = 1 if body.get("enabled") else 0
        elif new_st == "approved":
            new_en = 1
        elif new_st in ("pending", "rejected"):
            new_en = 0
        else:
            new_en = old_en
        cur.execute(
            """UPDATE cf_telegram_user SET display_name=?, member_id=?, enabled=?, notes=?,
            status=?, telegram_username=COALESCE(NULLIF(?,''), telegram_username),
            updated_at=datetime('now') WHERE id=?""",
            (
                str(body.get("display_name") or ""),
                body.get("member_id"),
                new_en,
                str(body.get("notes") or ""),
                new_st,
                str(body.get("telegram_username") or ""),
                tid,
            ),
        )
        conn.commit()
        return 200, {"ok": True}

    if path == "/api/admin/notify-prefs":
        nid = int(body.get("id") or 0)
        if nid < 1:
            return 400, "id required"
        cur.execute(
            """UPDATE cf_notify_pref SET mqtt_offline=?, daily_news=?, weather_brief=?,
            ai_alerts=?, updated_at=datetime('now') WHERE id=?""",
            (
                1 if body.get("mqtt_offline", True) else 0,
                1 if body.get("daily_news", True) else 0,
                1 if body.get("weather_brief", True) else 0,
                1 if body.get("ai_alerts", False) else 0,
                nid,
            ),
        )
        conn.commit()
        return 200, {"ok": True}

    return 404, "not found"


def handle_admin_delete(
    conn: sqlite3.Connection,
    path: str,
    qs: dict[str, list[str]],
    headers: Any | None = None,
) -> tuple[int, dict | str]:
    _ensure_admin_tables(conn)
    cur = conn.cursor()
    rid = int((qs.get("id") or ["0"])[0] or 0)

    if path == "/api/admin/farm-diary" and rid > 0:
        cur.execute("DELETE FROM cf_farm_diary WHERE id=?", (rid,))
        conn.commit()
        return 200, {"ok": True}

    if path == "/api/admin/telegram-users" and rid > 0:
        ok, _, err = _require_admin(conn, headers or {})
        if not ok:
            return err  # type: ignore[return-value]
        cur.execute("DELETE FROM cf_telegram_user WHERE id=?", (rid,))
        conn.commit()
        return 200, {"ok": True}

    return 404, "not found"


def _auth_status(site_host: str = "") -> dict:
    """Google OAuth·nginx 상태 요약."""
    env_path = Path("/etc/cronusfarm/oauth2-proxy.env")
    client_ok = False
    redirect = ""
    if env_path.is_file():
        text = env_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("OAUTH2_PROXY_CLIENT_ID="):
                v = line.split("=", 1)[1].strip()
                client_ok = len(v) > 8
            if line.startswith("OAUTH2_PROXY_REDIRECT_URL="):
                redirect = line.split("=", 1)[1].strip()

    def svc(name: str) -> str:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return (r.stdout or "").strip() or "unknown"
        except Exception:
            return "unknown"

    oauth_svc = svc("cronusfarm-oauth2-proxy.service")
    nginx_st = svc("nginx")
    if oauth_svc == "active" and client_ok:
        login = "active"
    elif client_ok:
        login = "configured_not_running"
    else:
        login = "not_configured"

    host = (site_host or "").strip().lower()
    oauth_hosts = ("cronusfarm.duckdns.org",)
    oauth_for_site = host in oauth_hosts or any(
        host.endswith("." + d) for d in oauth_hosts
    )

    return {
        "nginx": nginx_st,
        "oauth2_proxy": oauth_svc,
        "google_client_configured": client_ok,
        "redirect_url": redirect,
        "google_login": login,
        "oauth_for_site": oauth_for_site,
        "site_host": host,
        "login_entry": "/oauth2/start",
        "hint": (
            "Google 로그인은 cronusfarm.duckdns.org 전용. "
            "Tailscale(*.ts.net)은 VPN 인증만 OAuth 없음."
        ),
    }


def _handle_reset(target: str) -> tuple[int, dict | str]:
    # r4 / r3 = 펌웨어 업로드(긴 작업), r4-soft / r3-soft = 시리얼 리셋만
    scripts = {
        "ida": _ROOT / "scripts" / "pi-reset-ida-services.sh",
        "r3": _ROOT / "scripts" / "pi-reset-r3-panel.sh",
        "r3-soft": _ROOT / "scripts" / "pi-reset-r3-soft.sh",
        "r4": _ROOT / "scripts" / "pi-reset-r4-main.sh",
        "r4-soft": _ROOT / "scripts" / "pi-reset-r4.sh",
    }
    timeouts = {
        "ida": 120,
        "r3": 180,
        "r3-soft": 45,
        "r4": 300,
        "r4-soft": 45,
    }
    # 펌웨어 업로드는 bridge HTTP 스레드를 막지 않도록 백그라운드 실행
    async_targets = frozenset({"ida", "r3", "r4"})
    if target not in scripts:
        return 404, "unknown reset target"
    sh = scripts[target]
    if not sh.is_file():
        return 500, {"ok": False, "error": f"missing {sh}"}
    log_dir = Path("/tmp/cf_reset_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"reset_{target}.log"
    timeout = timeouts.get(target, 120)
    try:
        with open(log_file, "ab") as logf:
            logf.write(f"\n--- reset {target} ---\n".encode())
            if target in async_targets:
                proc = subprocess.Popen(
                    ["bash", str(sh)],
                    cwd=str(_ROOT),
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, "CRONUS_ROOT": str(_ROOT)},
                    start_new_session=True,
                )
                return 202, {
                    "ok": True,
                    "target": target,
                    "started": True,
                    "pid": proc.pid,
                    "log": str(log_file),
                    "hint": "백그라운드 실행 — log_tail은 완료 후 확인",
                }
            proc = subprocess.run(
                ["bash", str(sh)],
                cwd=str(_ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env={**os.environ, "CRONUS_ROOT": str(_ROOT)},
            )
        ok = proc.returncode == 0
        tail = ""
        if log_file.is_file():
            raw = log_file.read_bytes()
            tail = raw[-2000:].decode("utf-8", errors="replace")
        return (
            200 if ok else 500,
            {
                "ok": ok,
                "target": target,
                "exit_code": proc.returncode,
                "log_tail": tail,
            },
        )
    except subprocess.TimeoutExpired:
        return 504, {"ok": False, "error": "timeout", "target": target}
    except Exception as e:
        return 500, {"ok": False, "error": str(e), "target": target}


def _today_kst() -> str:
    import datetime as dt

    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")


def _ai_diagnose(body: dict) -> tuple[int, dict | str]:
    crop = str(body.get("crop") or "작물").strip()
    symptoms = str(body.get("symptoms") or body.get("note") or "").strip()
    image_b64 = str(body.get("image_base64") or "").strip()
    host = os.environ.get("CRONUSFARM_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("CRONUSFARM_OLLAMA_MODEL", "gemma:2b").strip()
    vision = os.environ.get("CRONUSFARM_OLLAMA_VISION_MODEL", "").strip()

    ctx = []
    if symptoms:
        ctx.append(f"관찰·증상 설명: {symptoms}")
    if image_b64:
        if vision:
            ctx.append("(첨부 사진 있음 — 비전 모델로 분석 시도)")
        else:
            ctx.append(
                "(사진 첨부됨. 비전 모델 미설정 — 증상 설명과 아래 일반 지식으로 진단합니다. "
                "Pi에 llava 등 설치 후 CRONUSFARM_OLLAMA_VISION_MODEL 설정 권장)"
            )

    prompt = (
        f"당신은 시설원예·노지 농업 전문 컨설턴트입니다. 작물: {crop}\n"
        + "\n".join(ctx)
        + "\n\n병해충·생리장해·영양결핍 가능성을 구분해 한국어로 요약하고, "
        "즉시 조치·예방·전국 예찰 참고(농촌진흥청)를 bullet로 제시하세요. "
        "확실하지 않으면 추가 관찰 포인트를 명시하세요."
    )

    payload: dict[str, Any] = {
        "model": vision if (image_b64 and vision) else model,
        "prompt": prompt,
        "stream": False,
    }
    if image_b64 and vision:
        try:
            raw = base64.b64decode(image_b64.split(",", 1)[-1])
            payload["images"] = [base64.b64encode(raw).decode("ascii")]
        except Exception:
            pass

    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("response") or "").strip()
        if not text:
            text = "(Ollama 응답 없음)"
        return 200, {
            "ok": True,
            "crop": crop,
            "diagnosis": text,
            "model": payload["model"],
            "vision_used": bool(image_b64 and vision),
        }
    except urllib.error.URLError as e:
        return 503, {
            "ok": False,
            "error": f"Ollama 연결 실패: {e}",
            "hint": "Pi에서 ollama serve 및 CRONUSFARM_OLLAMA_HOST 확인",
        }
