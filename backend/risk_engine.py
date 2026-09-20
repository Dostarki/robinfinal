"""Port of analyseRisk() + goplusReport() from scripts/serve-app.js and scripts/risk-metadata.js."""
import asyncio
import hashlib
import json
import time
from urllib.parse import quote

from core import RISK_CHAINS, http, new_id, now_ms

_cache: dict[str, dict] = {}
_goplus_token_cache: dict = {}


class RiskError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def truth(value):
    return value is True or value == "1" or value == 1


def flag(value):
    if isinstance(value, dict):
        return truth(value.get("status"))
    return truth(value)


def safety_level(score):
    return "low" if score >= 80 else "moderate" if score >= 55 else "high" if score >= 30 else "critical"


def asset_key(chain, address):
    return chain + ":" + (address if chain == "solana" else address.lower())


SOLANA_CATALOG = [
    ["Mint authority enabled", "A mint authority can create additional supply."],
    ["Freeze authority enabled", "A freeze authority can restrict token-account activity."],
    ["Balance authority enabled", "A privileged authority can alter token-account balances."],
    ["Closable token accounts", "A privileged authority can close token accounts."],
    ["Restricted default account state", "New token accounts can begin in a restricted state."],
    ["Default account state upgradeable", "The default account policy can be changed."],
    ["Transfer fee enabled", "Transfers can carry a token-level fee."],
    ["Transfer fee upgradeable", "A privileged authority can change transfer fees."],
    ["Transfer hook enabled", "Transfers invoke supplementary program logic."],
    ["Transfer hook upgradeable", "Supplementary transfer logic can be changed."],
    ["Non-transferable token", "The token cannot be freely transferred."],
    ["Independent high-risk signal", "The independent Solana validation source returned a high-risk signal."],
]
EVM_CATALOG = [
    ["Honeypot signal", "The primary provider flags potential sell restriction behavior."],
    ["Swap simulation flagged honeypot", "The independent swap simulation indicates a potential honeypot."],
    ["Mint authority enabled", "A privileged role may increase token supply."],
    ["Freeze authority enabled", "A privileged role may freeze balances or transfers."],
    ["Blacklist capability", "The contract has blacklist-related controls."],
    ["Hidden owner", "The contract may retain undisclosed privileged ownership."],
    ["Upgradeable proxy", "Contract logic may be changed after deployment."],
    ["Transfers can be paused", "A privileged role may pause token transfers."],
    ["Source code not verified", "The provider does not report verified source code."],
    ["High buy tax", "The reported buy tax exceeds the review threshold."],
    ["High sell tax", "The reported sell tax exceeds the review threshold."],
]


def risk_criteria(chain, signals):
    catalog = SOLANA_CATALOG if chain == "solana" else EVM_CATALOG
    result = []
    for title, note in catalog:
        finding = next((s for s in signals if s["title"] == title), None)
        result.append({"title": title, "note": note, "status": "warning" if finding else "clear", "points": finding["weight"] if finding else 0})
    return result


def goplus_report(chain, address, data):
    result = data.get("result") if isinstance(data, dict) else None
    source = {}
    if isinstance(result, dict):
        source = result.get(address.lower()) or result.get(address) or result
    if not isinstance(source, dict):
        source = {}
    signals = []

    def add(when, weight, title):
        if when:
            signals.append({"title": title, "weight": weight})

    def num(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    if chain == "solana":
        metadata = source.get("metadata") or {}
        add(flag(source.get("mintable")), 18, "Mint authority enabled")
        add(flag(source.get("freezable")), 15, "Freeze authority enabled")
        add(flag(source.get("balance_mutable_authority")), 16, "Balance authority enabled")
        add(flag(source.get("closable")), 10, "Closable token accounts")
        add(flag(source.get("default_account_state")), 10, "Restricted default account state")
        add(flag(source.get("default_account_state_upgradable")), 8, "Default account state upgradeable")
        add(flag(source.get("transfer_fee")), 8, "Transfer fee enabled")
        add(flag(source.get("transfer_fee_upgradable")), 10, "Transfer fee upgradeable")
        add(flag(source.get("transfer_hook")), 8, "Transfer hook enabled")
        add(flag(source.get("transfer_hook_upgradable")), 10, "Transfer hook upgradeable")
        add(flag(source.get("non_transferable")), 20, "Non-transferable token")
        return {"name": metadata.get("name") or source.get("token_name") or source.get("name") or "Unknown token", "symbol": metadata.get("symbol") or source.get("token_symbol") or source.get("symbol") or "—",
                "logo": metadata.get("logo") or metadata.get("image") or source.get("logo_url") or source.get("logo") or None, "marketCapUsd": num(source.get("market_cap")) or None, "creatorAddress": source.get("creator_address") or None, "signals": signals}

    add(truth(source.get("is_honeypot")), 45, "Honeypot signal")
    add(truth(source.get("is_mintable")), 18, "Mint authority enabled")
    add(truth(source.get("is_freezable")), 15, "Freeze authority enabled")
    add(truth(source.get("is_blacklisted")), 18, "Blacklist capability")
    add(truth(source.get("hidden_owner")), 15, "Hidden owner")
    add(truth(source.get("is_proxy")), 8, "Upgradeable proxy")
    add(truth(source.get("transfer_pausable")), 12, "Transfers can be paused")
    add("is_open_source" in source and not truth(source.get("is_open_source")), 10, "Source code not verified")
    add(num(source.get("buy_tax")) > 10, 12, "High buy tax")
    add(num(source.get("sell_tax")) > 10, 16, "High sell tax")
    return {"name": source.get("token_name") or source.get("name") or "Unknown token", "symbol": source.get("token_symbol") or source.get("symbol") or "—", "logo": source.get("logo_url") or source.get("logo") or None,
            "marketCapUsd": num(source.get("market_cap")) or None, "creatorAddress": source.get("creator_address") or None, "signals": signals}


async def upstream(url, headers=None, body=None, timeout=60):
    client = http()
    try:
        if body is not None:
            response = await client.post(url, headers=headers or {}, content=body, timeout=timeout)
        else:
            response = await client.get(url, headers=headers or {}, timeout=timeout)
    except Exception as error:
        raise RiskError(f"Upstream unavailable: {error.__class__.__name__}", 502)
    if response.status_code >= 400:
        raise RiskError(f"Upstream {response.status_code}", 502)
    return response.json()


async def goplus_token(pool, entry):
    cached = _goplus_token_cache
    if cached.get("expires", 0) > now_ms() and cached.get("keyId") == entry["keyId"]:
        return cached["value"]
    stamp = int(time.time())
    sign = hashlib.sha1((entry["secret"] + str(stamp) + entry["appSecret"]).encode()).hexdigest()
    payload = await upstream("https://api.gopluslabs.io/api/v1/token", {"Content-Type": "application/json"}, json.dumps({"app_key": entry["secret"], "time": stamp, "sign": sign}))
    result = payload.get("result") or {}
    value = result.get("access_token") or payload.get("access_token")
    if not value:
        raise RiskError("GoPlus authentication failed", 502)
    expires_in = int(result.get("expires_in") or payload.get("expires_in") or 300)
    _goplus_token_cache.update({"keyId": entry["keyId"], "value": value, "expires": now_ms() + max(1000, expires_in * 1000 - 60000)})
    return value


async def upstream_pooled(pool, provider, url):
    if not pool.configured(provider):
        return await upstream(url)
    client = http()
    for _ in range(3):
        entry = pool.get_key(provider)
        if not entry:
            break
        status = None
        try:
            token = entry["secret"]
            if entry.get("kind") == "app":
                token = await goplus_token(pool, entry)
            # GoPlus validates this endpoint with the raw access token.
            headers = {"Authorization": token} if provider == "GoPlus" else {"Authorization": "Bearer " + token}
            response = await client.get(url, headers=headers, timeout=60)
            status = response.status_code
            if status >= 400:
                raise RiskError("Provider request failed", 502)
            body = response.json()
            if body.get("code") is not None and int(body.get("code")) != 1:
                raise RiskError("Provider response error", 502)
            pool.record_usage(entry["keyId"], True, status)
            return body
        except Exception:
            pool.record_usage(entry["keyId"], False, status)
            if status in (400, 401, 403):
                raise RiskError("Provider authorization or request rejected", status)
    # Fall back to the public endpoint when no eligible key is left.
    return await upstream(url)


async def fetch_token_market_data(chain, address):
    if chain not in RISK_CHAINS:
        return None
    key = "market:" + asset_key(chain, address)
    cached = _cache.get(key)
    if cached and cached["expires"] > now_ms():
        return cached["value"]
    try:
        response = await http().get("https://api.dexscreener.com/tokens/v1/" + chain + "/" + quote(address), timeout=20)
        if response.status_code >= 400:
            return None
        pairs = response.json()
        if not isinstance(pairs, list) or not pairs:
            return None
        matching = [p for p in pairs if asset_key(chain, (p.get("baseToken") or {}).get("address") or "x") == asset_key(chain, address)]
        matching.sort(key=lambda p: -float(((p.get("liquidity") or {}).get("usd")) or 0))
        best = matching[0] if matching else pairs[0]
        logo = None
        image = (best.get("info") or {}).get("imageUrl")
        if isinstance(image, str) and image.startswith("https://") and "dexscreener.com" in image.split("/")[2]:
            logo = image
        base_token = best.get("baseToken") or {}
        result = {"logo": logo, "marketCapUsd": float(best.get("marketCap") or best.get("fdv") or 0) or None, "fdvUsd": float(best.get("fdv") or 0) or None, "priceUsd": float(best.get("priceUsd") or 0) or None,
                  "name": base_token.get("name"), "symbol": base_token.get("symbol"), "dexId": best.get("dexId"), "pairAddress": best.get("pairAddress")}
        _cache[key] = {"value": result, "expires": now_ms() + 600_000}
        while len(_cache) > 1000:
            _cache.pop(next(iter(_cache)))
        return result
    except Exception:
        return None


async def analyse_risk(pool, chain, address, progress=None):
    """Run the full safety assessment. `progress(stage, percent)` is optional."""
    async def report_progress(stage, percent):
        if progress:
            await progress(stage, percent)

    await report_progress("Checking token", 10)
    if chain == "solana":
        go_url = "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses=" + quote(address)
    else:
        go_url = "https://api.gopluslabs.io/api/v1/token_security/" + RISK_CHAINS[chain] + "?contract_addresses=" + quote(address)
    providers = ["GoPlus"]
    go_data = await upstream_pooled(pool, "GoPlus", go_url)
    if go_data.get("code") and int(go_data.get("code")) != 1:
        raise RiskError("GoPlus analysis unavailable", 502)
    primary = goplus_report(chain, address, go_data)
    if not (go_data.get("result") or {}) and primary["name"] == "Unknown token":
        raise RiskError("No security data was returned for this token on the selected network.", 404)
    signals = list(primary["signals"])

    await report_progress("Checking signals", 40)
    if primary["marketCapUsd"] is None or primary["logo"] is None:
        market = await fetch_token_market_data(chain, address)
        if market:
            if primary["marketCapUsd"] is None and market.get("marketCapUsd") is not None:
                primary["marketCapUsd"] = market["marketCapUsd"]
            if not primary["logo"] and market.get("logo"):
                primary["logo"] = market["logo"]
            if primary["name"] == "Unknown token" and market.get("name"):
                primary["name"] = market["name"]
            if primary["symbol"] == "—" and market.get("symbol"):
                primary["symbol"] = market["symbol"]

    if chain == "solana":
        report = None
        for attempt in range(2):
            try:
                report = await upstream("https://api.rugcheck.xyz/v1/tokens/" + quote(address) + "/report/summary", {"User-Agent": "Robinity-Risk/1.0"}, timeout=20)
                if report:
                    break
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(0.4)
        if report:
            providers.append("RugCheck")
            try:
                normalised = float(report.get("score_normalised") or report.get("score") or 0)
            except (TypeError, ValueError):
                normalised = 0
            if normalised >= 7000:
                signals.append({"title": "Independent high-risk signal", "weight": 15})
    else:
        try:
            check = await upstream("https://api.honeypot.is/v2/IsHoneypot?address=" + quote(address) + "&chainID=" + RISK_CHAINS[chain], timeout=20)
            providers.append("Honeypot.is")
            if (check.get("honeypotResult") or {}).get("isHoneypot") is True:
                signals.append({"title": "Swap simulation flagged honeypot", "weight": 35})
        except Exception:
            pass

    risk_score = min(100, sum(s["weight"] for s in signals))
    score = 100 - risk_score
    return {"id": new_id(), "chain": chain, "address": address, "name": primary["name"], "symbol": primary["symbol"], "logo": primary["logo"], "marketCapUsd": primary["marketCapUsd"], "creatorAddress": primary["creatorAddress"],
            "score": score, "riskScore": risk_score, "severity": safety_level(score), "signals": signals[:8], "criteria": risk_criteria(chain, signals), "providers": providers, "analysisVersion": "TEST-SAFETY-v1", "analyzedAt": now_ms(), "freshness": "live", "cached": False}
