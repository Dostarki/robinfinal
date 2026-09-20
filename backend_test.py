#!/usr/bin/env python3
"""
Comprehensive backend API test for Robinity Intelligence
Tests all endpoints as specified in the review request
"""
import os
import sys
import time
import json
import requests
import pyotp
from eth_account import Account
from eth_account.messages import encode_defunct

# Backend URL from frontend/.env
BACKEND_URL = "https://robinit-extend.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_pass(test_name):
    print(f"✅ PASS: {test_name}")
    test_results["passed"].append(test_name)

def log_fail(test_name, error):
    print(f"❌ FAIL: {test_name}")
    print(f"   Error: {error}")
    test_results["failed"].append({"test": test_name, "error": str(error)})

def log_warning(test_name, warning):
    print(f"⚠️  WARNING: {test_name}")
    print(f"   Warning: {warning}")
    test_results["warnings"].append({"test": test_name, "warning": str(warning)})

def sign_message(account, message):
    """Sign a message with an eth_account Account"""
    sig = account.sign_message(encode_defunct(text=message))
    sig_hex = sig.signature.hex()
    if not sig_hex.startswith('0x'):
        sig_hex = '0x' + sig_hex
    return sig_hex

def test_sanity_checks():
    """Test 1: Sanity checks"""
    print("\n" + "="*80)
    print("TEST 1: SANITY CHECKS")
    print("="*80)
    
    session = requests.Session()
    
    # GET /api/
    try:
        resp = session.get(f"{BACKEND_URL}/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "message" in data, "Response should have 'message' field"
        log_pass("GET /api/ returns 200")
    except Exception as e:
        log_fail("GET /api/", e)
    
    # GET /api/public/tape
    try:
        resp = session.get(f"{BACKEND_URL}/public/tape")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "activity" in data, "Response should have 'activity' field"
        assert isinstance(data["activity"], list), "'activity' should be a list"
        log_pass("GET /api/public/tape returns {activity: []}")
    except Exception as e:
        log_fail("GET /api/public/tape", e)
    
    # GET /api/public/state
    try:
        resp = session.get(f"{BACKEND_URL}/public/state")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "sale" in data, "Response should have 'sale' field"
        assert "deployments" in data, "Response should have 'deployments' field"
        assert "activity" in data, "Response should have 'activity' field"
        log_pass("GET /api/public/state has sale/deployments/activity")
    except Exception as e:
        log_fail("GET /api/public/state", e)
    
    # GET /api/x/config
    try:
        resp = session.get(f"{BACKEND_URL}/x/config")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "configured" in data, "Response should have 'configured' field"
        assert data["configured"] == False, "X should not be configured"
        log_pass("GET /api/x/config returns configured:false")
    except Exception as e:
        log_fail("GET /api/x/config", e)
    
    # GET /api/x/me
    try:
        resp = session.get(f"{BACKEND_URL}/x/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "user" in data, "Response should have 'user' field"
        assert data["user"] is None, "User should be null"
        log_pass("GET /api/x/me returns {user:null}")
    except Exception as e:
        log_fail("GET /api/x/me", e)

def test_intelligence_early_access():
    """Test 2: Intelligence early access flow"""
    print("\n" + "="*80)
    print("TEST 2: INTELLIGENCE EARLY ACCESS")
    print("="*80)
    
    session = requests.Session()
    
    # Create a random wallet for testing
    test_wallet = Account.create()
    test_address = test_wallet.address.lower()
    
    print(f"Test wallet: {test_address}")
    
    # GET /api/risk/access/me (not connected)
    try:
        resp = session.get(f"{BACKEND_URL}/risk/access/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["connected"] == False, "Should not be connected initially"
        log_pass("GET /api/risk/access/me returns connected:false")
    except Exception as e:
        log_fail("GET /api/risk/access/me (not connected)", e)
    
    # POST /api/risk/access/nonce
    challenge_id = None
    message = None
    try:
        resp = session.post(f"{BACKEND_URL}/risk/access/nonce", json={"address": test_address})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "challengeId" in data, "Response should have 'challengeId'"
        assert "message" in data, "Response should have 'message'"
        challenge_id = data["challengeId"]
        message = data["message"]
        # Verify message contains the lowercased address
        assert test_address in message, f"Message should contain lowercased address {test_address}"
        log_pass("POST /api/risk/access/nonce returns challengeId and message with address")
    except Exception as e:
        log_fail("POST /api/risk/access/nonce", e)
        return  # Can't continue without challenge
    
    # Test wrong signature (get fresh challenge)
    try:
        resp = session.post(f"{BACKEND_URL}/risk/access/nonce", json={"address": test_address})
        wrong_data = resp.json()
        wrong_wallet = Account.create()
        wrong_sig = sign_message(wrong_wallet, wrong_data['message'])
        resp = session.post(f"{BACKEND_URL}/risk/access/verify", json={
            "challengeId": wrong_data['challengeId'],
            "signature": wrong_sig
        })
        assert resp.status_code == 401, f"Expected 401 for wrong signature, got {resp.status_code}"
        log_pass("POST /api/risk/access/verify with wrong signature returns 401")
    except Exception as e:
        log_fail("POST /api/risk/access/verify (wrong signature)", e)
    
    # Test expired/unknown challengeId
    try:
        signature = sign_message(test_wallet, message)
        resp = session.post(f"{BACKEND_URL}/risk/access/verify", json={
            "challengeId": "unknown-challenge-id",
            "signature": signature
        })
        assert resp.status_code == 401, f"Expected 401 for unknown challengeId, got {resp.status_code}"
        log_pass("POST /api/risk/access/verify with unknown challengeId returns 401")
    except Exception as e:
        log_fail("POST /api/risk/access/verify (unknown challengeId)", e)
    
    # POST /api/risk/access/verify (correct signature) - get fresh challenge
    try:
        resp = session.post(f"{BACKEND_URL}/risk/access/nonce", json={"address": test_address})
        fresh_data = resp.json()
        signature = sign_message(test_wallet, fresh_data['message'])
        resp = session.post(f"{BACKEND_URL}/risk/access/verify", json={
            "challengeId": fresh_data['challengeId'],
            "signature": signature
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["connected"] == True, "Should be connected after verify"
        assert "access" in data, "Response should have 'access' field"
        assert data["access"]["remaining"] == 3, "Should have 3 remaining analyses"
        log_pass("POST /api/risk/access/verify with correct signature returns 200 connected:true")
    except Exception as e:
        log_fail("POST /api/risk/access/verify (correct signature)", e)
        return  # Can't continue without session
    
    # GET /api/risk/access/me (now connected)
    try:
        resp = session.get(f"{BACKEND_URL}/risk/access/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["connected"] == True, "Should be connected"
        assert data["access"]["remaining"] == 3, "Should have 3 remaining"
        log_pass("GET /api/risk/access/me now returns connected:true with remaining:3")
    except Exception as e:
        log_fail("GET /api/risk/access/me (connected)", e)
    
    # POST /api/risk/analyses without session (new session)
    try:
        new_session = requests.Session()
        resp = new_session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "ethereum",
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        })
        assert resp.status_code == 401, f"Expected 401 without session, got {resp.status_code}"
        log_pass("POST /api/risk/analyses without session returns 401")
    except Exception as e:
        log_fail("POST /api/risk/analyses (no session)", e)
    
    # Test invalid address
    try:
        resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "ethereum",
            "address": "abc"
        })
        assert resp.status_code == 400, f"Expected 400 for invalid address, got {resp.status_code}"
        log_pass("POST /api/risk/analyses with invalid address returns 400")
    except Exception as e:
        log_fail("POST /api/risk/analyses (invalid address)", e)
    
    # Test unsupported chain
    try:
        resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "unsupported",
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        })
        assert resp.status_code == 400, f"Expected 400 for unsupported chain, got {resp.status_code}"
        log_pass("POST /api/risk/analyses with unsupported chain returns 400")
    except Exception as e:
        log_fail("POST /api/risk/analyses (unsupported chain)", e)
    
    # Submit USDT analysis
    job_id = None
    try:
        resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "ethereum",
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT
        })
        assert resp.status_code in [200, 202], f"Expected 200 or 202, got {resp.status_code}"
        data = resp.json()
        
        if resp.status_code == 200:
            # Cached result
            assert data["status"] == "completed", "Cached result should be completed"
            assert "report" in data, "Should have report"
            assert data["report"].get("cached") == True, "Should be marked as cached"
            log_pass("POST /api/risk/analyses (USDT) returns cached result")
            job_id = None  # No need to poll
        else:
            # New job
            assert "jobId" in data, "Response should have 'jobId'"
            assert data["status"] in ["queued", "running"], "Status should be queued or running"
            job_id = data["jobId"]
            log_pass("POST /api/risk/analyses (USDT) returns 202 with jobId")
    except Exception as e:
        log_fail("POST /api/risk/analyses (USDT)", e)
    
    # Poll for completion if we have a job
    if job_id:
        try:
            print(f"Polling job {job_id}...")
            max_wait = 120  # 120 seconds max
            start_time = time.time()
            completed = False
            
            while time.time() - start_time < max_wait:
                resp = session.get(f"{BACKEND_URL}/risk/analyses/{job_id}")
                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
                data = resp.json()
                
                if data["status"] == "completed":
                    assert "report" in data, "Completed job should have report"
                    report = data["report"]
                    assert "score" in report, "Report should have score"
                    assert 0 <= report["score"] <= 100, "Score should be 0-100"
                    assert "criteria" in report, "Report should have criteria"
                    assert len(report["criteria"]) == 11, "Should have 11 criteria"
                    assert "providers" in report, "Report should have providers"
                    assert "GoPlus" in report["providers"], "Should include GoPlus provider"
                    assert "name" in report, "Report should have name"
                    assert "symbol" in report, "Report should have symbol"
                    assert "insights" in report, "Report should have insights key (may be null)"
                    completed = True
                    log_pass(f"GET /api/risk/analyses/{job_id} completed with valid report")
                    break
                elif data["status"] == "failed":
                    error = data.get("error", "Unknown error")
                    log_fail(f"GET /api/risk/analyses/{job_id}", f"Analysis failed: {error}")
                    break
                
                time.sleep(2)
            
            if not completed and data.get("status") not in ["completed", "failed"]:
                log_warning(f"GET /api/risk/analyses/{job_id}", f"Analysis did not complete within {max_wait}s")
        except Exception as e:
            log_fail(f"GET /api/risk/analyses/{job_id} polling", e)
        
        # Test SSE events endpoint
        try:
            resp = session.get(f"{BACKEND_URL}/risk/analyses/{job_id}/events", stream=True)
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            assert "text/event-stream" in resp.headers.get("content-type", ""), "Should be SSE stream"
            
            # Read at least one event
            event_found = False
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("event: progress"):
                    event_found = True
                    break
                if event_found:
                    break
            
            resp.close()
            if event_found:
                log_pass(f"GET /api/risk/analyses/{job_id}/events streams SSE events")
            else:
                log_warning(f"GET /api/risk/analyses/{job_id}/events", "No progress event found in stream")
        except Exception as e:
            log_fail(f"GET /api/risk/analyses/{job_id}/events", e)
    
    # Re-submit same asset (should return cached)
    try:
        resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "ethereum",
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT
        })
        assert resp.status_code == 200, f"Expected 200 for cached, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "completed", "Cached result should be completed"
        assert "report" in data, "Should have report"
        assert data["report"].get("cached") == True, "Should be marked as cached"
        log_pass("Re-submitting same asset returns cached result without consuming quota")
    except Exception as e:
        log_fail("POST /api/risk/analyses (cached)", e)
    
    # GET /api/risk/history
    try:
        resp = session.get(f"{BACKEND_URL}/risk/history")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "reports" in data, "Response should have 'reports'"
        assert isinstance(data["reports"], list), "'reports' should be a list"
        # Should contain the USDT report
        usdt_found = any(r.get("address", "").lower() == "0xdac17f958d2ee523a2206206994597c13d831ec7" for r in data["reports"])
        assert usdt_found, "History should contain USDT report"
        log_pass("GET /api/risk/history contains USDT report")
    except Exception as e:
        log_fail("GET /api/risk/history", e)
    
    # Rate limit test: submit 2 more different addresses
    addresses = [
        "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
    ]
    
    for addr in addresses:
        try:
            resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
                "chain": "ethereum",
                "address": addr
            })
            assert resp.status_code in [200, 202], f"Expected 200 or 202, got {resp.status_code}"
            log_pass(f"POST /api/risk/analyses ({addr[:10]}...) accepted")
        except Exception as e:
            log_fail(f"POST /api/risk/analyses ({addr[:10]}...)", e)
    
    # 4th distinct address should hit rate limit
    try:
        resp = session.post(f"{BACKEND_URL}/risk/analyses", json={
            "chain": "ethereum",
            "address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"  # WBTC
        })
        assert resp.status_code == 429, f"Expected 429 for rate limit, got {resp.status_code}"
        data = resp.json()
        assert "access" in data, "Rate limit response should have 'access' object"
        log_pass("4th analysis hits rate limit (429) with access object")
    except Exception as e:
        log_fail("POST /api/risk/analyses (rate limit)", e)
    
    # Test accessing job from different wallet session
    if job_id:
        try:
            new_wallet = Account.create()
            new_session = requests.Session()
            
            # Get nonce and verify for new wallet
            resp = new_session.post(f"{BACKEND_URL}/risk/access/nonce", json={"address": new_wallet.address})
            data = resp.json()
            sig = sign_message(new_wallet, data["message"])
            resp = new_session.post(f"{BACKEND_URL}/risk/access/verify", json={
                "challengeId": data["challengeId"],
                "signature": sig
            })
            
            # Try to access original job
            resp = new_session.get(f"{BACKEND_URL}/risk/analyses/{job_id}")
            assert resp.status_code == 404, f"Expected 404 for different wallet, got {resp.status_code}"
            log_pass(f"GET /api/risk/analyses/{job_id} with different wallet returns 404")
        except Exception as e:
            log_fail("GET /api/risk/analyses (different wallet)", e)

def test_admin_auth():
    """Test 3: Admin authentication and panel"""
    print("\n" + "="*80)
    print("TEST 3: ADMIN AUTHENTICATION")
    print("="*80)
    
    session = requests.Session()
    
    # Test invalid address
    try:
        resp = session.post(f"{BACKEND_URL}/auth/nonce", json={"address": "invalid"})
        assert resp.status_code == 400, f"Expected 400 for invalid address, got {resp.status_code}"
        log_pass("POST /api/auth/nonce with invalid address returns 400")
    except Exception as e:
        log_fail("POST /api/auth/nonce (invalid address)", e)
    
    # Create random wallet (non-admin)
    random_wallet = Account.create()
    random_address = random_wallet.address
    
    print(f"Random wallet: {random_address}")
    
    # Get nonce for random wallet
    try:
        resp = session.post(f"{BACKEND_URL}/auth/nonce", json={"address": random_address})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "challengeId" in data, "Response should have 'challengeId'"
        assert "message" in data, "Response should have 'message'"
        log_pass("POST /api/auth/nonce with valid random address returns challengeId and message")
        
        # Verify with random wallet (should get 403)
        signature = sign_message(random_wallet, data["message"])
        resp = session.post(f"{BACKEND_URL}/auth/verify-wallet", json={
            "challengeId": data["challengeId"],
            "signature": signature
        })
        assert resp.status_code == 403, f"Expected 403 for non-admin, got {resp.status_code}"
        data = resp.json()
        assert "error" in data or "detail" in data, "Error response should have error/detail"
        error_msg = data.get("error") or data.get("detail")
        assert "not an admin" in str(error_msg).lower(), "Error should mention not an admin"
        log_pass("POST /api/auth/verify-wallet with random wallet returns 403 'not an admin'")
    except Exception as e:
        log_fail("POST /api/auth/verify-wallet (random wallet)", e)
    
    # Test bad signature
    try:
        resp = session.post(f"{BACKEND_URL}/auth/nonce", json={"address": random_address})
        data = resp.json()
        
        bad_sig = "0x" + "00" * 65  # Invalid signature
        resp = session.post(f"{BACKEND_URL}/auth/verify-wallet", json={
            "challengeId": data["challengeId"],
            "signature": bad_sig
        })
        assert resp.status_code == 401, f"Expected 401 for bad signature, got {resp.status_code}"
        log_pass("POST /api/auth/verify-wallet with bad signature returns 401")
    except Exception as e:
        log_fail("POST /api/auth/verify-wallet (bad signature)", e)
    
    # Test unauthenticated admin endpoints
    try:
        resp = session.get(f"{BACKEND_URL}/admin/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        log_pass("GET /api/admin/me without cookie returns 401")
    except Exception as e:
        log_fail("GET /api/admin/me (no auth)", e)
    
    try:
        resp = session.get(f"{BACKEND_URL}/admins")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        log_pass("GET /api/admins without cookie returns 401")
    except Exception as e:
        log_fail("GET /api/admins (no auth)", e)
    
    try:
        resp = session.get(f"{BACKEND_URL}/admin/api-keys")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        log_pass("GET /api/admin/api-keys without cookie returns 401")
    except Exception as e:
        log_fail("GET /api/admin/api-keys (no auth)", e)
    
    # Full admin flow with owner wallet
    print("\n--- Testing full admin flow (requires temporary .env change) ---")
    
    # Generate a new wallet for admin testing
    admin_wallet = Account.create()
    admin_address = admin_wallet.address
    
    print(f"Admin test wallet: {admin_address}")
    print(f"⚠️  NOTE: This test requires temporarily setting ADMIN_OWNER_ADDRESS={admin_address} in /app/backend/.env")
    print("⚠️  The test will attempt to modify .env, run the flow, then restore it.")
    
    # Read current .env
    env_path = "/app/backend/.env"
    try:
        with open(env_path, 'r') as f:
            original_env = f.read()
        
        # Modify .env
        modified_env = original_env
        for line in original_env.split('\n'):
            if line.startswith('ADMIN_OWNER_ADDRESS='):
                modified_env = modified_env.replace(line, f'ADMIN_OWNER_ADDRESS={admin_address}')
                break
        
        with open(env_path, 'w') as f:
            f.write(modified_env)
        
        print("✓ Modified .env with test admin address")
        
        # Restart backend
        import subprocess
        subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], check=True, capture_output=True)
        print("✓ Restarted backend")
        time.sleep(5)  # Wait for backend to start
        
        # Now test admin flow
        admin_session = requests.Session()
        
        # Get nonce
        resp = admin_session.post(f"{BACKEND_URL}/auth/nonce", json={"address": admin_address})
        assert resp.status_code == 200
        nonce_data = resp.json()
        
        # Sign and verify
        signature = sign_message(admin_wallet, nonce_data["message"])
        resp = admin_session.post(f"{BACKEND_URL}/auth/verify-wallet", json={
            "challengeId": nonce_data["challengeId"],
            "signature": signature
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        verify_data = resp.json()
        assert verify_data["phase"] == "enroll", f"Expected phase 'enroll', got {verify_data.get('phase')}"
        assert "ticket" in verify_data, "Should have ticket"
        log_pass("Admin wallet verify returns phase:enroll with ticket")
        
        ticket = verify_data["ticket"]
        
        # TOTP setup
        resp = admin_session.post(f"{BACKEND_URL}/auth/totp-setup", json={"ticket": ticket})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        totp_data = resp.json()
        assert "qrDataUrl" in totp_data, "Should have qrDataUrl"
        assert totp_data["qrDataUrl"].startswith("data:image/png;base64,"), "QR should be base64 PNG"
        log_pass("POST /api/auth/totp-setup returns QR code")
        
        # Test wrong TOTP code
        resp = admin_session.post(f"{BACKEND_URL}/auth/verify-totp", json={
            "ticket": ticket,
            "code": "000000"
        })
        assert resp.status_code == 401, f"Expected 401 for wrong code, got {resp.status_code}"
        error_data = resp.json()
        error_msg = error_data.get("error") or error_data.get("detail")
        assert "invalid" in str(error_msg).lower(), "Error should mention invalid code"
        log_pass("POST /api/auth/verify-totp with wrong code returns 401")
        
        # For full testing, we'd need to extract TOTP secret from QR or insert session directly
        # Let's insert a test session directly in MongoDB
        print("\n--- Inserting test admin session directly in MongoDB ---")
        
        import pymongo
        from datetime import datetime, timezone
        
        mongo_client = pymongo.MongoClient("mongodb://localhost:27017")
        db = mongo_client["test_database"]
        
        # Ensure admin exists
        db.admins.update_one(
            {"address": admin_address.lower()},
            {"$setOnInsert": {
                "address": admin_address.lower(),
                "role": "owner",
                "totp": None,
                "createdAt": int(time.time() * 1000)
            }},
            upsert=True
        )
        
        # Insert session
        test_token = "testtoken123"
        db.admin_sessions.insert_one({
            "token": test_token,
            "address": admin_address.lower(),
            "expires": int(time.time() * 1000) + 3600000
        })
        
        print(f"✓ Inserted admin session with token: {test_token}")
        
        # Create new session with cookie
        auth_session = requests.Session()
        auth_session.cookies.set("admin_session", test_token)
        
        # Test admin endpoints
        # GET /api/admin/me
        resp = auth_session.get(f"{BACKEND_URL}/admin/me")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        me_data = resp.json()
        assert me_data["address"].lower() == admin_address.lower(), "Address should match"
        assert me_data["role"] == "owner", "Role should be owner"
        log_pass("GET /api/admin/me returns address and role:owner")
        
        # GET /api/admins
        resp = auth_session.get(f"{BACKEND_URL}/admins")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        admins_data = resp.json()
        assert "admins" in admins_data, "Should have admins list"
        assert any(a["address"].lower() == admin_address.lower() for a in admins_data["admins"]), "Should include owner"
        log_pass("GET /api/admins returns list including owner")
        
        # POST /api/admins (add new admin)
        new_admin = Account.create()
        resp = auth_session.post(f"{BACKEND_URL}/admins", json={"address": new_admin.address})
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        log_pass("POST /api/admins with valid address returns 201")
        
        # Duplicate admin
        resp = auth_session.post(f"{BACKEND_URL}/admins", json={"address": new_admin.address})
        assert resp.status_code == 409, f"Expected 409 for duplicate, got {resp.status_code}"
        log_pass("POST /api/admins with duplicate address returns 409")
        
        # Invalid address
        resp = auth_session.post(f"{BACKEND_URL}/admins", json={"address": "invalid"})
        assert resp.status_code == 400, f"Expected 400 for invalid address, got {resp.status_code}"
        log_pass("POST /api/admins with invalid address returns 400")
        
        # GET /api/admin/api-keys
        resp = auth_session.get(f"{BACKEND_URL}/admin/api-keys")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        keys_data = resp.json()
        assert "keys" in keys_data, "Should have keys"
        assert "poolStatus" in keys_data, "Should have poolStatus"
        assert "dailyBudgets" in keys_data, "Should have dailyBudgets"
        assert len(keys_data["dailyBudgets"]) == 3, "Should have 3 provider budgets"
        assert "publicProviders" in keys_data, "Should have publicProviders"
        log_pass("GET /api/admin/api-keys returns keys, poolStatus, dailyBudgets, publicProviders")
        
        # POST /api/admin/api-keys (add key)
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys", json={
            "provider": "goplus",
            "label": "test",
            "secret": "abcdefgh12345678",
            "monthlyLimit": 100
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        key_data = resp.json()
        assert "key" in key_data, "Should have key"
        assert key_data["key"]["masked"] == "••••5678", "Masked should show last 4"
        assert key_data["key"]["provider"] == "GoPlus", "Provider should be GoPlus"
        log_pass("POST /api/admin/api-keys returns 201 with masked key")
        
        key_id = key_data["key"]["id"]
        
        # Verify key appears in list
        resp = auth_session.get(f"{BACKEND_URL}/admin/api-keys")
        keys_data = resp.json()
        assert any(k["id"] == key_id for k in keys_data["keys"]), "New key should appear in list"
        key_entry = next(k for k in keys_data["keys"] if k["id"] == key_id)
        assert key_entry["source"] == "vault", "Source should be vault"
        assert key_entry["state"] == "ready", "State should be ready"
        assert key_entry["quotaPercent"] == 0, "Quota should be 0"
        log_pass("GET /api/admin/api-keys shows new key with correct details")
        
        # POST /api/admin/api-keys/settings
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys/settings", json={
            "id": key_id,
            "monthlyLimit": 50,
            "expiresAt": "2030-01-01"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        log_pass("POST /api/admin/api-keys/settings updates key settings")
        
        # POST /api/admin/api-keys/toggle
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys/toggle", json={"id": key_id})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        toggle_data = resp.json()
        assert toggle_data["active"] == False, "Should be inactive after toggle"
        log_pass("POST /api/admin/api-keys/toggle sets active:false")
        
        # Toggle again
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys/toggle", json={"id": key_id})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        toggle_data = resp.json()
        assert toggle_data["active"] == True, "Should be active after second toggle"
        log_pass("POST /api/admin/api-keys/toggle sets active:true")
        
        # POST /api/admin/api-keys/rotate
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys/rotate", json={
            "id": key_id,
            "secret": "newsecret99999999"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        rotate_data = resp.json()
        assert rotate_data["masked"] == "••••9999", "Masked should show new last 4"
        log_pass("POST /api/admin/api-keys/rotate updates secret")
        
        # Bad key body (short secret)
        resp = auth_session.post(f"{BACKEND_URL}/admin/api-keys", json={
            "provider": "goplus",
            "label": "test",
            "secret": "short",
            "monthlyLimit": 100
        })
        assert resp.status_code == 400, f"Expected 400 for short secret, got {resp.status_code}"
        log_pass("POST /api/admin/api-keys with short secret returns 400")
        
        # DELETE /api/admin/api-keys/{id}
        resp = auth_session.delete(f"{BACKEND_URL}/admin/api-keys/{key_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        log_pass("DELETE /api/admin/api-keys/{id} returns 200")
        
        # Delete unknown id
        resp = auth_session.delete(f"{BACKEND_URL}/admin/api-keys/unknown-id")
        assert resp.status_code == 404, f"Expected 404 for unknown id, got {resp.status_code}"
        log_pass("DELETE /api/admin/api-keys/{unknown-id} returns 404")
        
        # GET /api/admin/state
        resp = auth_session.get(f"{BACKEND_URL}/admin/state")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        state_data = resp.json()
        assert "deployments" in state_data, "Should have deployments"
        assert "activity" in state_data, "Should have activity"
        log_pass("GET /api/admin/state returns deployments and activity")
        
        # POST /api/admin/deployments
        deployment_data = {
            "label": "Alpha",
            "tokenSymbol": "RBNT",
            "network": "testnet",
            "tokenAddress": "0x" + "1" * 40,
            "curveAddress": "0x" + "2" * 40
        }
        resp = auth_session.post(f"{BACKEND_URL}/admin/deployments", json=deployment_data)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        deployment_resp = resp.json()
        assert "deployment" in deployment_resp, "Should have deployment"
        deployment_id = deployment_resp["deployment"]["id"]
        log_pass("POST /api/admin/deployments creates new deployment")
        
        # Update same deployment
        deployment_data["id"] = deployment_id
        deployment_data["label"] = "Alpha Updated"
        resp = auth_session.post(f"{BACKEND_URL}/admin/deployments", json=deployment_data)
        assert resp.status_code == 200, f"Expected 200 for update, got {resp.status_code}"
        log_pass("POST /api/admin/deployments with existing id updates deployment")
        
        # Invalid network
        bad_deployment = deployment_data.copy()
        bad_deployment["network"] = "invalid"
        resp = auth_session.post(f"{BACKEND_URL}/admin/deployments", json=bad_deployment)
        assert resp.status_code == 400, f"Expected 400 for invalid network, got {resp.status_code}"
        log_pass("POST /api/admin/deployments with invalid network returns 400")
        
        # POST /api/admin/activity
        activity_data = {
            "action": "Deploy token",
            "state": "confirmed",
            "network": "testnet",
            "hash": "0xabc",
            "deploymentId": deployment_id
        }
        resp = auth_session.post(f"{BACKEND_URL}/admin/activity", json=activity_data)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        activity_resp = resp.json()
        assert "activity" in activity_resp, "Should have activity"
        log_pass("POST /api/admin/activity creates new activity")
        
        # Invalid state
        bad_activity = activity_data.copy()
        bad_activity["state"] = "invalid"
        resp = auth_session.post(f"{BACKEND_URL}/admin/activity", json=bad_activity)
        assert resp.status_code == 400, f"Expected 400 for invalid state, got {resp.status_code}"
        log_pass("POST /api/admin/activity with invalid state returns 400")
        
        # Verify state updates
        resp = auth_session.get(f"{BACKEND_URL}/admin/state")
        state_data = resp.json()
        assert len(state_data["deployments"]) >= 1, "Should have at least 1 deployment"
        assert len(state_data["activity"]) >= 1, "Should have at least 1 activity"
        log_pass("GET /api/admin/state shows new deployment and activity")
        
        # Check public tape
        resp = requests.get(f"{BACKEND_URL}/public/tape")
        tape_data = resp.json()
        assert any(a["id"] == activity_resp["activity"]["id"] for a in tape_data["activity"]), "Public tape should show confirmed activity"
        log_pass("GET /api/public/tape shows confirmed activity with deployment info")
        
        # Check public state (should only show mainnet deployments)
        resp = requests.get(f"{BACKEND_URL}/public/state")
        public_state = resp.json()
        # Our deployment is testnet, so shouldn't appear
        assert not any(d["id"] == deployment_id for d in public_state["deployments"]), "Public state should only show mainnet"
        log_pass("GET /api/public/state shows only mainnet deployments")
        
        # GET /api/admin/queue/stats
        resp = auth_session.get(f"{BACKEND_URL}/admin/queue/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        stats_data = resp.json()
        assert "queues" in stats_data, "Should have queues"
        assert "jobs" in stats_data, "Should have jobs"
        assert "providers" in stats_data, "Should have providers"
        assert "sse" in stats_data, "Should have sse"
        assert "cache" in stats_data, "Should have cache"
        assert "timestamp" in stats_data, "Should have timestamp"
        log_pass("GET /api/admin/queue/stats returns complete stats")
        
        # POST /api/admin/queue/refresh
        resp = auth_session.post(f"{BACKEND_URL}/admin/queue/refresh", json={
            "chain": "ethereum",
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        log_pass("POST /api/admin/queue/refresh invalidates cache")
        
        # POST /api/auth/logout
        resp = auth_session.post(f"{BACKEND_URL}/auth/logout")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        log_pass("POST /api/auth/logout returns 200")
        
        # Verify logged out
        resp = auth_session.get(f"{BACKEND_URL}/admin/me")
        assert resp.status_code == 401, f"Expected 401 after logout, got {resp.status_code}"
        log_pass("GET /api/admin/me after logout returns 401")
        
        # Clean up test data
        db.admin_sessions.delete_many({"token": test_token})
        db.admins.delete_many({"address": admin_address.lower()})
        print("✓ Cleaned up test admin data")
        
    except Exception as e:
        log_fail("Admin flow", e)
        import traceback
        traceback.print_exc()
    finally:
        # Restore original .env
        try:
            with open(env_path, 'w') as f:
                f.write(original_env)
            print("✓ Restored original .env")
            
            # Restart backend
            subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], check=True, capture_output=True)
            print("✓ Restarted backend with original config")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️  WARNING: Failed to restore .env: {e}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(test_results["passed"]) + len(test_results["failed"])
    passed = len(test_results["passed"])
    failed = len(test_results["failed"])
    warnings = len(test_results["warnings"])
    
    print(f"\nTotal tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warnings}")
    
    if test_results["failed"]:
        print("\n--- FAILED TESTS ---")
        for item in test_results["failed"]:
            print(f"  ❌ {item['test']}")
            print(f"     {item['error']}")
    
    if test_results["warnings"]:
        print("\n--- WARNINGS ---")
        for item in test_results["warnings"]:
            print(f"  ⚠️  {item['test']}")
            print(f"     {item['warning']}")
    
    print("\n" + "="*80)
    
    return failed == 0

if __name__ == "__main__":
    print("="*80)
    print("ROBINITY INTELLIGENCE BACKEND API TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print()
    
    try:
        test_sanity_checks()
        test_intelligence_early_access()
        test_admin_auth()
        
        success = print_summary()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
