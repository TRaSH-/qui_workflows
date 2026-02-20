#!/usr/bin/env python3
"""
qBittorrent Auto-Tagger Script (Hotio compatible)
Only tested on Hotio's qBit docker image

Features:
- Regex precompilation
- Async batching
- Tag de-duplication
- Retry + timeout handling
- No external dependencies

Usage in qBittorrent:
Tools -> Options -> Downloads -> Run external program on torrent added

Command:
python3 /config/qbittorrent_auto_tagger.py "%N" "%I"
"""

import re
import sys
import json
import time
import socket
import asyncio
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor

# ============================================================================
# CONFIGURATION
# ============================================================================

QBITTORRENT_HOST = "http://localhost:8080" # use container port
QBITTORRENT_USERNAME = "admin"
QBITTORRENT_PASSWORD = "adminadmin"

HTTP_TIMEOUT = 5        # seconds per request
HTTP_RETRIES = 5        # total attempts
RETRY_BACKOFF = 1.5     # exponential backoff base
ASYNC_WORKERS = 4       # concurrent API workers

RULES = [
    {
        "name": "Episode",
        "enabled": True,
        "tag": "Episode",
        "patterns": [
            r"(?i)S\d{1,3}E\d{1,3}",
            r"\b\d{4}\D+\d{2}\D+\d{2}\b"
        ],
        "exclude_patterns": []
    },
    {
        "name": "Season",
        "enabled": True,
        "tag": "Season",
        "patterns": [
            r"(?i)(?:S\d{1,3}|Season[\s\.]\d{1,3})"
        ],
        "exclude_patterns": [
            r"(?i)S\d{1,3}E\d{1,3}"
        ]
    },
    {
        "name": "Unmatched",
        "enabled": True,
        "tag": "Unmatched",
        "patterns": [],
        "exclude_patterns": [
            r"(?i)S\d{1,3}E\d{1,3}",
            r"\b\d{4}\D+\d{2}\D+\d{2}\b",
            r"(?i)(?:S\d{1,3}|Season[\s\.]\d{1,3})"
        ]
    }
]

# ============================================================================
# REGEX PRECOMPILATION
# ============================================================================

def compile_rules(rules):
    compiled = []
    for rule in rules:
        compiled.append({
            **rule,
            "patterns": [re.compile(p) for p in rule["patterns"]],
            "exclude_patterns": [re.compile(p) for p in rule["exclude_patterns"]],
        })
    return compiled


COMPILED_RULES = compile_rules(RULES)


def matches_pattern(text, patterns):
    return any(p.search(text) for p in patterns)

# ============================================================================
# QBittorrent API CLIENT (stdlib-only)
# ============================================================================

class QBittorrentAPI:
    def __init__(self, host, username, password):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password

        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

        self._login()

    def _request(self, method, path, data=None, params=None):
        last_error = None

        for attempt in range(1, HTTP_RETRIES + 1):
            try:
                url = f"{self.host}{path}"
                if params:
                    url += "?" + urllib.parse.urlencode(params)

                encoded = None
                if data:
                    encoded = urllib.parse.urlencode(data).encode("utf-8")

                req = urllib.request.Request(url, data=encoded, method=method)

                with self.opener.open(req, timeout=HTTP_TIMEOUT) as resp:
                    return resp.read().decode("utf-8")

            except (urllib.error.URLError, socket.timeout) as e:
                last_error = e
                if attempt < HTTP_RETRIES:
                    time.sleep(RETRY_BACKOFF ** attempt)
                else:
                    break

        raise Exception(f"API request failed after {HTTP_RETRIES} attempts: {last_error}")

    def _login(self):
        response = self._request(
            "POST",
            "/api/v2/auth/login",
            data={
                "username": self.username,
                "password": self.password
            }
        )
        if response.strip() != "Ok.":
            raise Exception(f"Failed to login to qBittorrent: {response}")

    def get_torrent_info(self, info_hash):
        response = self._request(
            "GET",
            "/api/v2/torrents/info",
            params={"hashes": info_hash}
        )
        torrents = json.loads(response)
        return torrents[0] if torrents else None

    def get_existing_tags(self, info_hash):
        torrent = self.get_torrent_info(info_hash)
        if not torrent:
            return set()
        tags = torrent.get("tags", "")
        return set(t.strip() for t in tags.split(",") if t.strip())

    def add_tag(self, info_hash, tag):
        existing = self.get_existing_tags(info_hash)
        if tag in existing:
            print(f"Tag '{tag}' already present, skipping")
            return False

        self._request(
            "POST",
            "/api/v2/torrents/addTags",
            data={"hashes": info_hash, "tags": tag}
        )
        return True

# ============================================================================
# TAG DETERMINATION
# ============================================================================

def determine_tag(torrent_name):
    for rule in COMPILED_RULES:
        if not rule["enabled"]:
            continue

        if rule["exclude_patterns"] and matches_pattern(
            torrent_name, rule["exclude_patterns"]
        ):
            continue

        if not rule["patterns"]:
            return rule["tag"]

        if matches_pattern(torrent_name, rule["patterns"]):
            return rule["tag"]

    return None

# ============================================================================
# ASYNC BATCHING
# ============================================================================

EXECUTOR = ThreadPoolExecutor(max_workers=ASYNC_WORKERS)

async def run_async(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(EXECUTOR, func, *args)


async def process_torrent(torrent_name, info_hash, api):
    tag = determine_tag(torrent_name)

    if not tag:
        print("No tag applied")
        return

    print(f"Applying tag: {tag}")
    await run_async(api.add_tag, info_hash, tag)

# ============================================================================
# ENTRYPOINT
# ============================================================================

def main():
    if len(sys.argv) < 3:
        print("Usage: script.py <torrent_name> <info_hash>")
        sys.exit(1)

    torrent_name = sys.argv[1]
    info_hash = sys.argv[2]

    api = QBittorrentAPI(
        QBITTORRENT_HOST,
        QBITTORRENT_USERNAME,
        QBITTORRENT_PASSWORD
    )

    asyncio.run(process_torrent(torrent_name, info_hash, api))


if __name__ == "__main__":
    main()
