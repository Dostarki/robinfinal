# Robinity Intelligence — PRD / Durum

## Amaç
- `/` : robinitypageX landing (X eklentisi dahil) — **dokunulmadı**.
- `/intelligence`, `/risk` : robinitmain Intelligence uygulaması (cüzdan erken erişim, kuyruklu analiz, creator intelligence).
- `/admin` : robinitmain admin paneli (cüzdan + TOTP, API key kasası, deployment/aktivite, kuyruk monitörü).
- `/legal`, `/methodology`, `/contact`, `/console` : pageX sayfaları.

## Backend (FastAPI + MongoDB) — Node `serve-app.js` portu
- `x_router.py` — X OAuth/görev/leaderboard (pageX'ten aynen).
- `admin_router.py` — /api/auth/*, /api/admin/*, /api/admins, /api/public/*.
- `risk_router.py` — /api/risk/access/*, /api/risk/analyses (job + SSE), /api/risk/history, /api/admin/queue/*.
- `risk_engine.py` — GoPlus + Honeypot.is + RugCheck + DexScreener skoru.
- `creator_service.py` — Helius / Etherscan / Bitquery creator intelligence.
- `key_pool.py` — AES-GCM şifreli vault + .env anahtar havuzu.

## Env (backend/.env)
ADMIN_OWNER_ADDRESS, ADMIN_AUTH_MASTER_KEY, GOPLUS_*, HELIUS_API_KEY, ETHERSCAN_API_KEY, BITQUERY_*, X_CLIENT_ID/SECRET/REDIRECT_URI, X_TASK_TWEET_URL.
- **Çoklu key (2026-06):** GOPLUS_ACCESS_TOKEN, GOPLUS_APP_KEY/GOPLUS_APP_SECRET (sıralı eşleşir), HELIUS_API_KEY, ETHERSCAN_API_KEY, BITQUERY_ACCESS_TOKEN virgülle ayrılmış liste kabul eder. Her key havuza ayrı girer (`env-goplus`, `env-goplus-2`, ...). Seçim: en az kullanılan önce; 429/401/403 veya GoPlus 40xx body kodu → 60s+ cooldown → sıradaki key; hiç uygun key kalmazsa public GoPlus endpoint'ine düşer.
- GoPlus token cache key bazlı (`_goplus_token_cache[keyId]`).
- Kullanıcının verdiği 2 GoPlus değeri (abng…, sje7…) GoPlus tarafından 4012 "signature verification failure" ile reddediliyor — muhtemelen App Key/Secret çifti eksik. Public fallback sayesinde analiz yine çalışıyor.

## Durum
- Backend: 61/61 test geçti. Frontend: ekran görüntüleri ile doğrulandı (desktop + mobil).
- Kuyruk: Redis/Postgres yerine Mongo + asyncio arka plan görevi (aynı API sözleşmesi).

## X Rewards admin sekmesi (2026-06) — `/admin` → "𝕏 X Rewards"
- `x_admin_router.py` → `/api/admin/x/*` (tüm adminler): `GET/PUT settings`, `POST/PUT/DELETE tasks`, `GET/POST users`, `PATCH/DELETE users/{x_id}`.
- Ayarlar `x_settings` koleksiyonunda (`key: "tasks"`); `.env` (X_TARGET_USERNAME, X_TASK_TWEET_URL, X_QUOTE_TEXT) yalnızca varsayılan. `x_router.task_config(db)` DB'yi okur.
- Özel görevler: `{id: custom-…, title, text, link, points, check: none|like_rt|quote, active}` → landing Tasks modalında "New" etiketiyle görünür; Tasks butonunda "N new" rozeti. `check=none` → "Claim" (doğrulamasız).
- Puan modeli: `user_points = Σ(tamamlanan görev puanı, güncel ayardan) + points_adjustment`. Admin toplam puanı yazınca `points_adjustment` hesaplanır.
- Manuel kullanıcı: `x_id: manual-…`, EVM girilirse liderlik tablosunda görünür.
- Admin sayfası açılışta `GET /api/admin/me` ile oturumu geri yükler (30 dk cookie).
- Test: `backend/tests/test_x_rewards.py` (22/22), frontend test ajanı ile uçtan uca geçti (`test_reports/iteration_1.json`).
- Test için: `/app/memory/test_credentials.md`. `X_DEV_MOCK` şu an 0.
