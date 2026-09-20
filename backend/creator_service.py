"""Port of scripts/risk-creator.js — creator / deployer intelligence (Helius, Etherscan, Bitquery)."""
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from core import http, normalize, now_ms

CHAINS = {"ethereum": "1", "bsc": "56", "base": "8453", "arbitrum": "42161", "optimism": "10", "polygon": "137"}
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
SOL = "So11111111111111111111111111111111111111112"
KNOWN_ERRORS = ["Daily request budget reached", "Provider quota reached", "Unavailable on this account or network", "Query unavailable on this account"]


def looks_like_pump_mint(value):
    return isinstance(value, str) and value.lower().endswith("pump")


def address_for(chain, value):
    if not isinstance(value, str):
        return None
    if chain == "solana":
        return value if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", value) else None
    if chain not in CHAINS:
        return None
    try:
        return normalize(value)
    except Exception:
        return None


def number(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if result == result and result not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def text(value):
    return value[:160] if isinstance(value, str) else ""


def iso_from_seconds(value):
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except Exception:
        return None


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ProviderError(Exception):
    pass


class CreatorService:
    def __init__(self, db, pool, request_timeout=60):
        self.db = db
        self.pool = pool
        self.timeout = request_timeout
        self.cache = {}
        self.inflight = {}
        self.usage = {"day": "", "counts": {}}
        self.limits = {"Helius": int(os.environ.get("HELIUS_DAILY_LIMIT", 2000)), "Bitquery": int(os.environ.get("BITQUERY_DAILY_LIMIT", 1000)), "Etherscan": int(os.environ.get("ETHERSCAN_DAILY_LIMIT", 2000))}
        self._etherscan_lock = asyncio.Lock()

    async def load(self):
        saved = await self.db.provider_usage.find_one({"_id": "daily"})
        if saved:
            self.usage = {"day": saved.get("day", ""), "counts": saved.get("counts", {})}

    def _reserve(self, provider):
        day = today()
        if self.usage["day"] != day:
            self.usage = {"day": day, "counts": {}}
        if self.usage["counts"].get(provider, 0) >= self.limits[provider]:
            raise ProviderError("Daily request budget reached")
        self.usage["counts"][provider] = self.usage["counts"].get(provider, 0) + 1
        asyncio.get_running_loop().create_task(self.db.provider_usage.update_one({"_id": "daily"}, {"$set": {"day": self.usage["day"], "counts": self.usage["counts"]}}, upsert=True))

    def usage_snapshot(self):
        day = today()
        return [{"provider": provider, "limit": limit, "used": self.usage["counts"].get(provider, 0) if self.usage["day"] == day else 0, "day": day} for provider, limit in self.limits.items()]

    async def request(self, provider, url, method="GET", headers=None, body=None):
        self._reserve(provider)
        client = http()
        attempts = min(3, max(1, len(self.pool.pools.get(provider) or [])))
        last_error = None
        for _ in range(attempts):
            entry = self.pool.get_key(provider)
            if not entry:
                break
            request_url, request_headers = url, dict(headers or {})
            if provider == "Etherscan":
                parts = urlparse(request_url)
                query = dict(parse_qsl(parts.query))
                query["apikey"] = entry["secret"]
                request_url = urlunparse(parts._replace(query=urlencode(query)))
            elif provider == "Helius":
                parts = urlparse(request_url)
                query = dict(parse_qsl(parts.query))
                if "api-key" in query or parts.hostname == "mainnet.helius-rpc.com":
                    query["api-key"] = entry["secret"]
                    request_url = urlunparse(parts._replace(query=urlencode(query)))
                request_headers["X-Api-Key"] = entry["secret"]
            elif provider == "Bitquery":
                request_headers["Authorization"] = "Bearer " + entry["secret"]
            status = None
            try:
                response = await client.request(method, request_url, headers=request_headers, content=body, timeout=self.timeout)
                status = response.status_code
                if status >= 400:
                    raise ProviderError("Provider quota reached" if status == 429 else "Unavailable on this account or network" if status == 403 else "Provider temporarily unavailable")
                data = response.json()
                if isinstance(data, dict) and (data.get("errors") or data.get("error") or (provider == "Etherscan" and data.get("status") != "1" and not re.search(r"no transactions found", str(data.get("message") or ""), re.I))):
                    raise ProviderError("Query unavailable on this account")
                self.pool.record_usage(entry["keyId"], True, status)
                return data
            except Exception as error:
                self.pool.record_usage(entry["keyId"], False, status)
                last_error = error if isinstance(error, ProviderError) else ProviderError("Provider temporarily unavailable")
        if last_error:
            raise last_error
        raise ProviderError("Provider quota reached")

    async def scan(self, params, scalar=False):
        async with self._etherscan_lock:  # at most ~2 Etherscan requests per second
            data = await self.request("Etherscan", "https://api.etherscan.io/v2/api?" + urlencode({**params, "apikey": ""}))
            await asyncio.sleep(0.55)
        if data.get("status") != "1" and not re.search(r"no transactions found", str(data.get("message") or ""), re.I):
            raise ProviderError("Unavailable on this account or network")
        result = data.get("result")
        if scalar:
            return result if isinstance(result, str) and result.isdigit() else None
        return result if isinstance(result, list) else []

    async def gql(self, query):
        return await self.request("Bitquery", "https://streaming.bitquery.io/graphql", "POST", {"Content-Type": "application/json"}, json.dumps({"query": query}))

    async def enrich(self, report):
        chain = report["chain"]
        asset = address_for(chain, report["address"])
        if not asset:
            raise ProviderError("Invalid asset")
        key = chain + ":" + asset
        cached = self.cache.get(key)
        if cached and cached["expires"] > now_ms():
            return {**cached["value"], "cached": True}
        if key in self.inflight:
            return await self.inflight[key]
        task = asyncio.get_running_loop().create_task(self._collect({**report, "address": asset}))
        self.inflight[key] = task
        try:
            value = await task
            self.cache[key] = {"value": value, "expires": now_ms() + (300_000 if value.get("creator") else 15_000)}
            while len(self.cache) > 300:
                self.cache.pop(next(iter(self.cache)))
            return value
        finally:
            self.inflight.pop(key, None)

    async def _collect(self, report):
        chain, address = report["chain"], report["address"]
        result = {"chain": chain, "address": address, "analyzedAt": now_ms(), "creator": None, "balances": None, "balanceHistory": None, "movements": None, "launches": None, "exchangeUsage": None,
                  "rugHistory": {"percent": None, "evaluated": 0, "note": "Verified historical launch outcomes are not available. A safety score is not a rug probability."}, "coverage": []}

        def status(provider, state, note):
            result["coverage"].append({"provider": provider, "state": state, "note": note})

        async def run(provider, task):
            try:
                await task()
                status(provider, "available", "Limited sample; not a complete wallet audit.")
            except Exception as error:
                message = str(error)
                status(provider, "unavailable", "Provider request timed out" if "Timeout" in error.__class__.__name__ else message if message in KNOWN_ERRORS else "Provider temporarily unavailable")

        pump_mint = chain == "solana" and looks_like_pump_mint(address)
        candidate = address_for(chain, report.get("creatorAddress"))
        if candidate and not pump_mint:
            result["creator"] = {"address": candidate, "verification": "Provider-reported creator; creation transaction not verified.", "source": "GoPlus"}

        if chain == "solana":
            await self._collect_solana(result, address, pump_mint, status, run)
        else:
            await self._collect_evm(result, chain, address, status, run)
        return result

    async def _collect_solana(self, result, address, pump_mint, status, run):
        chain = "solana"
        if self.pool.has_keys("Bitquery"):
            async def bitquery():
                query = f'query {{ Solana {{ Instructions(limit:{{count:1}},orderBy:{{ascending:Block_Time}},where:{{Transaction:{{Result:{{Success:true}}}},Instruction:{{Accounts:{{includes:{{Address:{{is:"{address}"}}}}}},Program:{{Address:{{is:"{PUMP}"}},Method:{{in:["create","create_v2"]}}}}}}}}) {{ Block {{ Time }} Transaction {{ Signer Signature }} Instruction {{ Program {{ Name Address Method }} }} }} }} }}'
                rows = ((((await self.gql(query)).get("data") or {}).get("Solana") or {}).get("Instructions") or [])
                creation = rows[0] if rows else None
                creator = address_for(chain, ((creation or {}).get("Transaction") or {}).get("Signer"))
                if not creator:
                    status("Creator", "unavailable", "No verified Pump.fun create transaction was found; pool and authority wallets are intentionally excluded." if pump_mint else "No Pump.fun creation transaction found for this mint.")
                    return
                result["creator"] = {"address": creator, "source": "Bitquery", "platform": "pump.fun", "verification": "Verified Pump.fun create transaction signer (the wallet that submitted token creation).", "transaction": text(creation["Transaction"].get("Signature")), "createdAt": text((creation.get("Block") or {}).get("Time"))}
                launches = await self.gql(f'query {{ Solana {{ TokenSupplyUpdates(limit:{{count:20}},orderBy:{{descending:Block_Time}},where:{{Transaction:{{Result:{{Success:true}},Signer:{{is:"{creator}"}}}},Instruction:{{Program:{{Address:{{is:"{PUMP}"}},Method:{{in:["create","create_v2"]}}}}}}}}) {{ Block {{ Time }} TokenSupplyUpdate {{ Currency {{ Symbol Name MintAddress }} }} Transaction {{ Signature }} }} }} }}')
                items = []
                for row in (((launches.get("data") or {}).get("Solana") or {}).get("TokenSupplyUpdates") or []):
                    currency = ((row.get("TokenSupplyUpdate") or {}).get("Currency") or {})
                    mint = address_for(chain, currency.get("MintAddress"))
                    if mint and mint != address:
                        items.append({"address": mint, "name": text(currency.get("Name")), "symbol": text(currency.get("Symbol")), "createdAt": text((row.get("Block") or {}).get("Time")), "kind": "Pump.fun token"})
                result["launches"] = {"items": list({item["address"]: item for item in items}.values()), "note": "Up to 20 recent Pump.fun creation events; current token excluded. Not all launch platforms."}
                trades = await self.gql(f'query {{ Solana {{ DEXTrades(limit:{{count:30}},orderBy:{{descending:Block_Time}},where:{{Transaction:{{Result:{{Success:true}},Signer:{{is:"{creator}"}}}}}}) {{ Transaction {{ Signature }} Trade {{ Dex {{ ProtocolName }} }} }} }} }}')
                rows = (((trades.get("data") or {}).get("Solana") or {}).get("DEXTrades") or [])
                result["exchangeUsage"] = {"swapTransactions": len({(r.get("Transaction") or {}).get("Signature") for r in rows if (r.get("Transaction") or {}).get("Signature")}), "cexTransfers": None,
                                           "labels": sorted({text(((r.get("Trade") or {}).get("Dex") or {}).get("ProtocolName")) for r in rows if text(((r.get("Trade") or {}).get("Dex") or {}).get("ProtocolName"))}),
                                           "note": "Up to 30 recent DEX trade rows by transaction signer, within the provider retention window. CEX usage is not covered."}
            await run("Bitquery", bitquery)
        else:
            status("Bitquery", "unconfigured", "Free trial is expired or its end date is not configured." if os.environ.get("BITQUERY_ACCESS_TOKEN") else "Creator launch history is not connected.")

        if not self.pool.has_keys("Helius"):
            status("Helius", "unconfigured", "Wallet data is not connected.")
            return

        rpc = "https://mainnet.helius-rpc.com/?api-key=pooled"
        if not result["creator"] and not pump_mint:
            try:
                das = await self.request("Helius", rpc, "POST", {"Content-Type": "application/json"}, json.dumps({"jsonrpc": "2.0", "id": "das-creator-lookup", "method": "getAsset", "params": {"id": address}}))
                asset = das.get("result") or {}
                fee_config = ((asset.get("mint_extensions") or {}).get("transfer_fee_config") or {})
                fee_auth = address_for(chain, fee_config.get("transfer_fee_config_authority") or fee_config.get("withdraw_withheld_authority"))
                creator = next((address_for(chain, c.get("address")) for c in asset.get("creators") or [] if address_for(chain, c.get("address"))), None)
                authority = next((address_for(chain, a.get("address")) for a in asset.get("authorities") or [] if address_for(chain, a.get("address"))), None)
                found = creator or fee_auth or authority
                if found:
                    result["creator"] = {"address": found, "source": "Helius", "verification": "Verified creator via Helius on-chain asset data." if creator else "Token fee authority identified via on-chain asset data." if fee_auth else "Token authority identified via Helius on-chain data (SPL/Token-2022)."}
                    status("Creator", "available", "Token authority identified via Helius on-chain asset data.")
            except Exception:
                pass

        if not result["creator"] and pump_mint:
            try:
                sig_data = await self.request("Helius", rpc, "POST", {"Content-Type": "application/json"}, json.dumps({"jsonrpc": "2.0", "id": "pump-create-lookup", "method": "getSignaturesForAddress", "params": [address, {"limit": 100}]}))
                sigs = sig_data.get("result") or []
                if sigs:
                    oldest = sigs[-1]
                    tx_data = await self.request("Helius", "https://api.helius.xyz/v0/transactions/?api-key=pooled", "POST", {"Content-Type": "application/json"}, json.dumps({"transactions": [oldest.get("signature")]}))
                    creator = address_for(chain, (tx_data[0] if isinstance(tx_data, list) and tx_data else {}).get("feePayer"))
                    if creator:
                        result["creator"] = {"address": creator, "source": "Helius", "platform": "pump.fun", "verification": "Verified Pump.fun token creation submitter (transaction feePayer).", "transaction": text(oldest.get("signature")), "createdAt": iso_from_seconds(oldest["blockTime"]) if oldest.get("blockTime") else None}
                        status("Creator", "available", "Verified Pump.fun creator via on-chain creation transaction.")
            except Exception:
                pass

        if not result["creator"]:
            status("Helius", "unavailable", "A verified Pump.fun creation signer is required before deployer wallet analysis." if pump_mint else "A creator address is required before wallet analysis.")
            return

        async def helius():
            wallet = result["creator"]["address"]

            async def balances():
                data = await self.request("Helius", f"https://api.helius.xyz/v1/wallet/{wallet}/balances?limit=20")
                result["balances"] = {"totalUsd": number(data.get("totalUsdValue")), "items": [{"symbol": text(item.get("symbol") or item.get("name")), "balance": number(item.get("balance")), "usd": number(item.get("usdValue"))} for item in (data.get("balances") or [])[:20]], "note": "Current holdings; first page of up to 20 assets."}

            async def history():
                data = await self.request("Helius", f"https://api.helius.xyz/v1/wallet/{wallet}/history?limit=30")
                rows = [row for row in data.get("data") or [] if not row.get("error")]
                items = []
                for row in rows:
                    for change in row.get("balanceChanges") or []:
                        if change.get("mint") in (SOL, "So11111111111111111111111111111111111111111", "11111111111111111111111111111111"):
                            items.append({"time": iso_from_seconds(row.get("timestamp")), "amount": number(change.get("amount")), "symbol": "SOL", "transaction": text(row.get("signature"))})
                result["movements"] = {"items": items[:12], "note": "Native SOL changes within up to 30 recent transactions, not historical wallet balances."}
                if not result["exchangeUsage"] and rows:
                    swaps, labels = set(), set()
                    for row in rows:
                        if row.get("type") == "SWAP" or row.get("source") in ("RAYDIUM", "ORCA", "JUPITER", "PUMP_FUN"):
                            if row.get("signature"):
                                swaps.add(row["signature"])
                            if row.get("source"):
                                labels.add(row["source"])
                    if swaps:
                        result["exchangeUsage"] = {"swapTransactions": len(swaps), "cexTransfers": None, "labels": sorted(labels), "note": "DEX activity observed from recent creator transactions via Helius."}

            async def balance_at(days):
                stamp = int((now_ms() - days * 86400000) / 1000)
                data = await self.request("Helius", f"https://api.helius.xyz/v1/wallet/{wallet}/balance-at?mint=So11111111111111111111111111111111111111111&time={stamp}")
                balance = number(data.get("balance"))
                if balance is not None:
                    result["balanceHistory"] = result["balanceHistory"] or {"items": [], "note": "Historical native SOL balance snapshots at ~7d and ~24h intervals."}
                    result["balanceHistory"]["items"].append({"time": iso_from_seconds(stamp), "balance": balance, "symbol": "SOL"})

            outcomes = await asyncio.gather(balances(), history(), balance_at(7), balance_at(1), return_exceptions=True)
            if result["balanceHistory"]:
                result["balanceHistory"]["items"].sort(key=lambda item: item["time"])
            failure = next((o for o in outcomes if isinstance(o, Exception)), None)
            if failure:
                raise failure
        await run("Helius", helius)

    async def _collect_evm(self, result, chain, address, status, run):
        chainid = CHAINS[chain]
        if not self.pool.has_keys("Etherscan"):
            status("Etherscan", "unconfigured", "Creator verification is not connected.")
            return

        async def etherscan():
            creations = await self.scan({"chainid": chainid, "module": "contract", "action": "getcontractcreation", "contractaddresses": address})
            creation = creations[0] if creations else {}
            creator = address_for(chain, creation.get("contractCreator"))
            if not creator:
                raise ProviderError("Provider temporarily unavailable")
            result["creator"] = {"address": creator, "source": "Etherscan", "verification": "Contract creation address; may be a factory, not the project operator.", "transaction": text(creation.get("txHash")), "createdAt": iso_from_seconds(creation["timestamp"]) if creation.get("timestamp") else None}
            rows = await self.scan({"chainid": chainid, "module": "account", "action": "txlist", "address": creator, "page": "1", "offset": "50", "sort": "desc"})
            items = []
            for row in rows:
                created = address_for(chain, row.get("contractAddress"))
                if row.get("isError") == "0" and (row.get("from") or "").lower() == creator and created and created != address:
                    items.append({"address": created, "name": "Contract deployment", "symbol": None, "kind": "Unverified contract", "createdAt": iso_from_seconds(row.get("timeStamp"))})
            result["launches"] = {"items": list({item["address"]: item for item in items}.values())[:20], "note": "Direct creations in the latest 50 normal transactions. Contracts are not necessarily tokens; factory/internal creations are not covered."}
            symbol = "BNB" if chain == "bsc" else "POL" if chain == "polygon" else "ETH"
            movements = []
            for row in rows:
                value = row.get("value") or ""
                if row.get("isError") == "0" and value.isdigit() and int(value) > 0:
                    outgoing, incoming = (row.get("from") or "").lower() == creator, (row.get("to") or "").lower() == creator
                    amount = 0 if outgoing == incoming else (-1 if outgoing else 1) * int(value) / 1e18
                    movements.append({"time": iso_from_seconds(row.get("timeStamp")), "amount": amount, "symbol": symbol, "transaction": text(row.get("hash"))})
            result["movements"] = {"items": movements[:12], "note": "Native movements in the latest 50 normal transactions. Excludes gas, internal transfers and token transfers; not a balance timeline."}
            wei = await self.scan({"chainid": chainid, "module": "account", "action": "balance", "address": creator, "tag": "latest"}, True)
            if wei is None:
                raise ProviderError("Provider temporarily unavailable")
            result["balances"] = {"totalUsd": None, "items": [{"symbol": symbol, "balance": int(wei) / 1e18, "usd": None}], "note": "Current native balance on the selected network. Other token holdings are not included."}
        await run("Etherscan", etherscan)
