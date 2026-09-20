"""Backend tests for X Rewards admin panel + landing plugin.

Covers:
  - Admin settings GET/PUT
  - Admin custom tasks CRUD
  - Public /api/x/config, /api/x/leaderboard
  - Admin manual users CRUD + PATCH (tasks, points, evm)
  - Mock X flow (dev-login) + verify custom task
  - Auth gating (401 without cookie)
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://robinit-extend.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "testadmintoken123"
ADMIN_COOKIES = {"admin_session": ADMIN_TOKEN}


# ─── fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def ensure_admin_session():
    # Seed admin_sessions document in Mongo
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    async def seed():
        c = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = c[os.environ.get("DB_NAME", "test_database")]
        await db.admin_sessions.update_one(
            {"token": ADMIN_TOKEN},
            {"$set": {"token": ADMIN_TOKEN,
                      "address": "0xb2f6409cf259b8820a733548f575d5b217ea4cce",
                      "expires": int((time.time() + 3600) * 1000)}},
            upsert=True,
        )
    asyncio.run(seed())
    yield


@pytest.fixture(scope="session")
def original_settings():
    r = requests.get(f"{BASE_URL}/api/admin/x/settings", cookies=ADMIN_COOKIES, timeout=15)
    return r.json() if r.status_code == 200 else None


# ─── settings ────────────────────────────────────────────────────────────────
class TestSettings:
    def test_settings_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/x/settings", timeout=15)
        assert r.status_code == 401

    def test_get_settings_ok(self):
        r = requests.get(f"{BASE_URL}/api/admin/x/settings", cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        data = r.json()
        for key in ("target_username", "tweet_url", "quote_text", "points", "custom_tasks", "source"):
            assert key in data

    def test_put_settings_saves(self):
        payload = {
            "target_username": "@RobinityInt",
            "tweet_url": "https://x.com/RobinityInt/status/1234567890",
            "quote_text": "Hello",
            "points": {"follow": 30, "like_rt": 15, "quote": 60},
        }
        r = requests.put(f"{BASE_URL}/api/admin/x/settings", json=payload, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] == "database"
        assert data["target_username"] == "RobinityInt"
        assert data["points"] == {"follow": 30, "like_rt": 15, "quote": 60}

    def test_put_settings_bad_username(self):
        r = requests.put(f"{BASE_URL}/api/admin/x/settings", json={
            "target_username": "not a name",
            "tweet_url": "",
            "quote_text": "x",
            "points": {"follow": 1, "like_rt": 1, "quote": 1},
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 400

    def test_put_settings_bad_tweet_url(self):
        r = requests.put(f"{BASE_URL}/api/admin/x/settings", json={
            "target_username": "RobinityInt",
            "tweet_url": "https://example.com/foo",
            "quote_text": "x",
            "points": {"follow": 1, "like_rt": 1, "quote": 1},
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 400


# ─── custom tasks ────────────────────────────────────────────────────────────
class TestCustomTasks:
    task_id = None

    def test_create_task(self):
        r = requests.post(f"{BASE_URL}/api/admin/x/tasks", json={
            "title": "TEST_JoinTG",
            "text": "Join our TG",
            "link": "https://t.me/robinity",
            "points": 25,
            "check": "none",
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 201, r.text
        task = r.json()["task"]
        assert task["id"].startswith("custom-")
        TestCustomTasks.task_id = task["id"]

    def test_create_quote_without_status_400(self):
        r = requests.post(f"{BASE_URL}/api/admin/x/tasks", json={
            "title": "TEST_Bad",
            "link": "https://x.com/robinit",
            "points": 10,
            "check": "quote",
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 400

    def test_update_task(self):
        assert TestCustomTasks.task_id
        r = requests.put(f"{BASE_URL}/api/admin/x/tasks/{TestCustomTasks.task_id}", json={
            "title": "TEST_JoinTG v2",
            "link": "https://t.me/robinity",
            "points": 30,
            "check": "none",
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        assert r.json()["task"]["points"] == 30

    def test_update_unknown_404(self):
        r = requests.put(f"{BASE_URL}/api/admin/x/tasks/custom-unknown", json={
            "title": "x", "points": 1, "check": "none",
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 404

    def test_public_config_reflects_task(self):
        r = requests.get(f"{BASE_URL}/api/x/config", timeout=15)
        assert r.status_code == 200
        ids = [t["id"] for t in r.json().get("custom_tasks", [])]
        assert TestCustomTasks.task_id in ids

    def test_leaderboard_total_tasks(self):
        r = requests.get(f"{BASE_URL}/api/x/leaderboard", timeout=15)
        assert r.status_code == 200
        cfg = requests.get(f"{BASE_URL}/api/x/config", timeout=15).json()
        expected = 3 + len(cfg["custom_tasks"])
        assert r.json()["total_tasks"] == expected


# ─── admin users ─────────────────────────────────────────────────────────────
class TestAdminUsers:
    x_id = None

    def test_users_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/x/users", timeout=15)
        assert r.status_code == 401

    def test_create_manual_user(self):
        r = requests.post(f"{BASE_URL}/api/admin/x/users", json={
            "username": "TEST_manualuser",
            "evm_address": "0x2222222222222222222222222222222222222222",
            "points": 100,
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 201, r.text
        user = r.json()["user"]
        assert user["x_id"].startswith("manual-")
        assert user["username"] == "TEST_manualuser"
        TestAdminUsers.x_id = user["x_id"]

    def test_duplicate_username_conflict(self):
        r = requests.post(f"{BASE_URL}/api/admin/x/users", json={
            "username": "test_manualuser",  # case-insensitive
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 409

    def test_invalid_evm(self):
        r = requests.post(f"{BASE_URL}/api/admin/x/users", json={
            "username": "TEST_evmbaduser",
            "evm_address": "0xnotanaddress",
        }, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 400

    def test_patch_task_awards_points(self):
        assert TestAdminUsers.x_id
        # First get baseline points
        r0 = requests.get(f"{BASE_URL}/api/admin/x/users", cookies=ADMIN_COOKIES, timeout=15)
        before = next(u for u in r0.json()["users"] if u["x_id"] == TestAdminUsers.x_id)["points"]
        r = requests.patch(f"{BASE_URL}/api/admin/x/users/{TestAdminUsers.x_id}",
                           json={"tasks": {"follow": True}}, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        after = r.json()["user"]["points"]
        assert after > before, f"points did not increase: {before} -> {after}"

    def test_patch_points_exact(self):
        r = requests.patch(f"{BASE_URL}/api/admin/x/users/{TestAdminUsers.x_id}",
                           json={"points": 500}, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["points"] == 500

    def test_patch_unset_evm(self):
        r = requests.patch(f"{BASE_URL}/api/admin/x/users/{TestAdminUsers.x_id}",
                           json={"evm_address": ""}, cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        assert not r.json()["user"].get("evm_address")

    def test_delete_user(self):
        r = requests.delete(f"{BASE_URL}/api/admin/x/users/{TestAdminUsers.x_id}", cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        r2 = requests.delete(f"{BASE_URL}/api/admin/x/users/{TestAdminUsers.x_id}", cookies=ADMIN_COOKIES, timeout=15)
        assert r2.status_code == 404


# ─── mock X flow ─────────────────────────────────────────────────────────────
class TestMockXFlow:
    def test_dev_login_and_verify(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/x/auth/dev-login", allow_redirects=False, timeout=15)
        assert r.status_code in (302, 307)
        assert "ri_x_session" in s.cookies.get_dict()

        # save evm (may be 409 if already saved)
        r = s.post(f"{BASE_URL}/api/x/evm",
                   json={"address": "0x1111111111111111111111111111111111111111"}, timeout=15)
        assert r.status_code in (200, 409)

        # get custom task id
        cfg = requests.get(f"{BASE_URL}/api/x/config", timeout=15).json()
        # pick a task with check=none
        candidate = next((t for t in cfg["custom_tasks"] if t.get("check") == "none"), None)
        if not candidate:
            pytest.skip("no custom task with check=none available")

        r = s.post(f"{BASE_URL}/api/x/tasks/{candidate['id']}/verify", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["points_awarded"] == candidate["points"]

        me = s.get(f"{BASE_URL}/api/x/me", timeout=15).json()
        assert me["user"]["points"] >= candidate["points"]

        # admin sees this user with the task done
        r = requests.get(f"{BASE_URL}/api/admin/x/users?q=robinity_tester",
                         cookies=ADMIN_COOKIES, timeout=15)
        assert r.status_code == 200
        users = r.json()["users"]
        found = next((u for u in users if u["username"] == "robinity_tester"), None)
        assert found is not None
        assert (found.get("tasks") or {}).get(candidate["id"], {}).get("done") is True


# ─── cleanup ─────────────────────────────────────────────────────────────────
class TestZCleanup:
    def test_cleanup_custom_task(self):
        if TestCustomTasks.task_id:
            r = requests.delete(f"{BASE_URL}/api/admin/x/tasks/{TestCustomTasks.task_id}",
                                cookies=ADMIN_COOKIES, timeout=15)
            assert r.status_code == 200
            r2 = requests.delete(f"{BASE_URL}/api/admin/x/tasks/{TestCustomTasks.task_id}",
                                 cookies=ADMIN_COOKIES, timeout=15)
            assert r2.status_code == 404

    def test_cleanup_dev_user(self):
        # Delete the mock user robinity_tester
        r = requests.get(f"{BASE_URL}/api/admin/x/users?q=robinity_tester",
                         cookies=ADMIN_COOKIES, timeout=15)
        for u in r.json().get("users", []):
            if u["username"] == "robinity_tester":
                requests.delete(f"{BASE_URL}/api/admin/x/users/{u['x_id']}",
                                cookies=ADMIN_COOKIES, timeout=15)
