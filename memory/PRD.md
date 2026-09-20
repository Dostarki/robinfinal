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

## Durum
- Backend: 61/61 test geçti. Frontend: ekran görüntüleri ile doğrulandı (desktop + mobil).
- Kuyruk: Redis/Postgres yerine Mongo + asyncio arka plan görevi (aynı API sözleşmesi).
