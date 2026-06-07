"""Minimal Morning (Green Invoice) API client.

Reads credentials from .env (MORNING_API_KEY / MORNING_API_SECRET).
Credentials are never logged or committed (.env is gitignored).
"""
import os
import time
import json
import requests

BASE = "https://api.greeninvoice.co.il/api/v1"


def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v
    return env


class Morning:
    def __init__(self, key=None, secret=None):
        env = load_env()
        self.key = key or env.get("MORNING_API_KEY") or os.environ.get("MORNING_API_KEY")
        self.secret = secret or env.get("MORNING_API_SECRET") or os.environ.get("MORNING_API_SECRET")
        if not self.key or not self.secret:
            raise RuntimeError("Missing MORNING_API_KEY / MORNING_API_SECRET")
        self.token = None
        self.token_exp = 0
        self.s = requests.Session()

    def authenticate(self):
        r = self.s.post(f"{BASE}/account/token",
                        json={"id": self.key, "secret": self.secret},
                        timeout=30)
        r.raise_for_status()
        data = r.json()
        self.token = data.get("token")
        self.token_exp = data.get("expires", 0)
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})
        return data

    def _ensure(self):
        if not self.token or time.time() > (self.token_exp - 60):
            self.authenticate()

    def post(self, path, payload):
        self._ensure()
        r = self.s.post(f"{BASE}{path}", json=payload, timeout=60)
        return r

    def get(self, path, params=None):
        self._ensure()
        r = self.s.get(f"{BASE}{path}", params=params, timeout=60)
        return r


if __name__ == "__main__":
    m = Morning()
    info = m.authenticate()
    masked = (m.token[:10] + "...") if m.token else None
    print("AUTH OK. token:", masked, "expires:", info.get("expires"))
