"""Port of scripts/key-pool.js — encrypted vault keys + .env fallback keys with usage tracking."""
import asyncio
import hashlib
import os
from datetime import datetime, timezone

from core import decrypt, now_ms

METRIC_FIELDS = ["requestCount", "successCount", "month", "monthlyRequests", "monthlySuccesses", "trackedSince", "lastUsedAt", "cooldownUntil", "consecutiveErrors", "lastStatus", "lastErrorAt", "configuredLimit", "configuredExpiry"]


def current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def parse_date_ms(value):
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


class KeyPool:
    def __init__(self, db):
        self.db = db
        self.pools: dict[str, list[dict]] = {}
        self.metrics: dict[str, dict] = {}
        self._loaded = False

    async def load(self):
        docs = await self.db.api_key_metrics.find({}, {"_id": 0}).to_list(2000)
        self.metrics = {doc["metricId"]: doc for doc in docs}
        await self.reload()
        self._loaded = True

    async def reload(self):
        pools: dict[str, list[dict]] = {}
        now = now_ms()
        env = os.environ

        def add(provider, entry):
            pools.setdefault(provider, []).append(entry)

        def base(key_id, secret, label, source, **extra):
            item = {"keyId": key_id, "secret": secret, "label": label, "source": source, "active": True, "monthlyLimit": 0, "requestCount": 0, "successCount": 0, "lastUsedAt": None, "cooldownUntil": None, "expiresAt": None, "consecutiveErrors": 0, "kind": None, "appSecret": None}
            item.update(extra)
            return item

        # 1. vault keys
        for item in await self.db.api_keys.find({}, {"_id": 0}).to_list(500):
            if not item.get("provider") or not item.get("encrypted"):
                continue
            try:
                secret = decrypt(item["encrypted"])
            except Exception:
                continue
            add(item["provider"], base(item["id"], secret, item.get("label", ""), "vault", active=item.get("active", True) is not False, monthlyLimit=int(item.get("monthlyLimit") or 0), requestCount=int(item.get("requestCount") or 0), successCount=int(item.get("successCount") or 0), expiresAt=item.get("expiresAt")))

        # 2. env fallback keys
        for provider, secret, expires in [("Helius", env.get("HELIUS_API_KEY"), None), ("Etherscan", env.get("ETHERSCAN_API_KEY"), None), ("Bitquery", env.get("BITQUERY_ACCESS_TOKEN"), parse_date_ms(env.get("BITQUERY_FREE_TRIAL_UNTIL")))]:
            secret = (secret or "").strip()
            if not secret or any(e["secret"] == secret for e in pools.get(provider, [])):
                continue
            add(provider, base("env-" + provider.lower(), secret, ".env", "env", expiresAt=expires))

        goplus_token = (env.get("GOPLUS_ACCESS_TOKEN") or "").strip()
        if goplus_token and not any(e["secret"] == goplus_token for e in pools.get("GoPlus", [])):
            add("GoPlus", base("env-goplus", goplus_token, ".env", "env"))
        app_key, app_secret = (env.get("GOPLUS_APP_KEY") or "").strip(), (env.get("GOPLUS_APP_SECRET") or "").strip()
        if app_key and app_secret:
            add("GoPlus", base("vault-app-goplus", app_key, "vault-app", "env", kind="app", appSecret=app_secret))

        for provider, pool in pools.items():
            for entry in pool:
                entry["metricId"] = hashlib.sha256(f"{provider}:{entry['keyId']}:{entry['secret']}".encode()).hexdigest()
                saved = self.metrics.get(entry["metricId"]) or {"month": current_month(), "monthlyRequests": 0, "monthlySuccesses": 0, "trackedSince": now}
                for field in METRIC_FIELDS:
                    if field in saved and saved[field] is not None or field in ("month", "monthlyRequests", "monthlySuccesses", "trackedSince"):
                        entry[field] = saved.get(field, entry.get(field))
                if entry.get("configuredLimit") is not None:
                    entry["monthlyLimit"] = entry["configuredLimit"]
                if "configuredExpiry" in saved:
                    entry["expiresAt"] = saved["configuredExpiry"]
                entry["inFlight"] = 0
        self.pools = pools

    def _persist(self):
        docs = []
        for pool in self.pools.values():
            for entry in pool:
                doc = {field: entry.get(field) for field in METRIC_FIELDS}
                doc["metricId"] = entry["metricId"]
                self.metrics[entry["metricId"]] = doc
                docs.append(doc)

        async def write():
            for doc in docs:
                await self.db.api_key_metrics.update_one({"metricId": doc["metricId"]}, {"$set": doc}, upsert=True)
        try:
            asyncio.get_running_loop().create_task(write())
        except RuntimeError:
            pass

    def state(self, entry):
        month = current_month()
        if entry.get("month") != month:
            entry.update({"month": month, "monthlyRequests": 0, "monthlySuccesses": 0})
        now = now_ms()
        if entry.get("active") is False:
            return "paused"
        if entry.get("expiresAt") and entry["expiresAt"] <= now:
            return "expired"
        if (entry.get("cooldownUntil") or 0) > now:
            return "cooldown"
        if (entry.get("monthlyLimit") or 0) > 0 and (entry.get("monthlyRequests") or 0) + (entry.get("inFlight") or 0) >= entry["monthlyLimit"]:
            return "quota reached"
        return "ready"

    def _find(self, key_id):
        for pool in self.pools.values():
            for entry in pool:
                if entry["keyId"] == key_id:
                    return entry
        return None

    def configure(self, key_id, monthly_limit, expires_at):
        entry = self._find(key_id)
        if not entry:
            return False
        entry.update({"monthlyLimit": monthly_limit, "configuredLimit": monthly_limit, "expiresAt": expires_at, "configuredExpiry": expires_at})
        self._persist()
        return True

    def get_key(self, provider):
        pool = self.pools.get(provider) or []
        eligible = [e for e in pool if self.state(e) == "ready"]
        if not eligible:
            return None
        eligible.sort(key=lambda e: ((e.get("monthlyRequests") or 0) + (e.get("inFlight") or 0), e.get("lastUsedAt") or 0))
        selected = eligible[0]
        selected["lastUsedAt"] = now_ms()
        selected["inFlight"] = (selected.get("inFlight") or 0) + 1
        return {"keyId": selected["keyId"], "secret": selected["secret"], "kind": selected.get("kind"), "appSecret": selected.get("appSecret")}

    def record_usage(self, key_id, success, status=None):
        entry = self._find(key_id)
        if not entry:
            return
        self.state(entry)
        now = now_ms()
        entry["inFlight"] = max(0, (entry.get("inFlight") or 0) - 1)
        entry["monthlyRequests"] = (entry.get("monthlyRequests") or 0) + 1
        entry["monthlySuccesses"] = (entry.get("monthlySuccesses") or 0) + (1 if success else 0)
        entry["lastStatus"] = status
        entry["requestCount"] = (entry.get("requestCount") or 0) + 1
        if success:
            entry["successCount"] = (entry.get("successCount") or 0) + 1
            entry["consecutiveErrors"] = 0
            entry["cooldownUntil"] = None
        else:
            entry["lastErrorAt"] = now
            entry["consecutiveErrors"] = (entry.get("consecutiveErrors") or 0) + 1
            if entry["consecutiveErrors"] >= 3 or status in (401, 403, 429):
                entry["cooldownUntil"] = now + 60_000
            if entry["consecutiveErrors"] >= 5:
                entry["cooldownUntil"] = now + 300_000
            if entry["consecutiveErrors"] >= 8:
                entry["cooldownUntil"] = now + 900_000
        entry["lastUsedAt"] = now
        self._persist()

    def has_keys(self, provider):
        return any(self.state(e) == "ready" for e in self.pools.get(provider) or [])

    def configured(self, provider):
        return bool(self.pools.get(provider))

    def snapshot(self):
        result = []
        for provider, pool in self.pools.items():
            total = 0
            for item in pool:
                self.state(item)
                total += item.get("monthlyRequests") or 0
            for entry in pool:
                state = self.state(entry)
                limit = entry.get("monthlyLimit") or 0
                monthly = entry.get("monthlyRequests") or 0
                result.append({"id": entry["keyId"], "provider": provider, "label": entry.get("label"), "source": entry["source"], "masked": "••••" + entry["secret"][-4:], "active": entry.get("active") is not False, "inPool": True, "state": state,
                               "monthlyLimit": limit, "requestCount": entry.get("requestCount") or 0, "successCount": entry.get("successCount") or 0, "monthlyRequests": monthly, "monthlySuccesses": entry.get("monthlySuccesses") or 0,
                               "quotaPercent": monthly / limit * 100 if limit > 0 else None, "trafficPercent": monthly / total * 100 if total > 0 else None,
                               "month": entry.get("month"), "trackedSince": entry.get("trackedSince"), "lastUsedAt": entry.get("lastUsedAt"), "lastStatus": entry.get("lastStatus"), "lastErrorAt": entry.get("lastErrorAt"),
                               "expiresAt": entry.get("expiresAt"), "cooldownUntil": entry.get("cooldownUntil"), "consecutiveErrors": entry.get("consecutiveErrors") or 0})
        return result

    def status(self):
        now = now_ms()
        result = {}
        for provider, pool in self.pools.items():
            result[provider] = {"total": len(pool), "active": sum(1 for e in pool if self.state(e) == "ready"), "inCooldown": sum(1 for e in pool if (e.get("cooldownUntil") or 0) > now), "expired": sum(1 for e in pool if e.get("expiresAt") and e["expiresAt"] <= now), "totalRequests": sum(e.get("requestCount") or 0 for e in pool)}
        return result
