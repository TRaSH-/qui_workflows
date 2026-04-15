#!/usr/bin/env python3
"""
qBittorrent Auto-Tagger Script (Hotio compatible)
Only tested on Hotio's qBit docker image

Features:
- Regex precompilation
- Tag de-duplication
- Lightweight: fails fast and silently if Web UI is unavailable
- Sends Accept-Encoding: gzip to avoid Qt 6.11.0 crash bug
- Handles gzip-compressed responses
- File logging with rotation
- Optional Discord error notifications
- No external dependencies

Usage in qBittorrent:
Tools -> Options -> Downloads -> Run external program on torrent added

Command:
python3 /config/scripts/qbittorrent_auto_tagger.py "%N" "%I"
"""

import re
import os
import sys
import gzip
import json
import time
import socket
import logging
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

# ============================================================================
# CONFIGURATION
# ============================================================================

QBITTORRENT_HOST     = "http://localhost:8080"
QBITTORRENT_USERNAME = "admin"
QBITTORRENT_PASSWORD = "adminadmin"

HTTP_TIMEOUT = 3    # seconds per request — keep short
HTTP_RETRIES = 3    # total attempts before giving up
RETRY_DELAY  = 2    # flat delay between retries (seconds)
# Worst-case runtime: HTTP_RETRIES * (HTTP_TIMEOUT + RETRY_DELAY) = ~15s

# Optional: Discord webhook URL for error notifications (leave empty to disable)
DISCORD_WEBHOOK_URL = ""

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
# LOGGING
# ============================================================================

LOG_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE     = os.path.join(LOG_DIR, "auto_tagger.log")
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB

os.makedirs(LOG_DIR, exist_ok=True)

# Simple rotation: if log exceeds max, rename to .old and start fresh
if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES:
    old = LOG_FILE + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.rename(LOG_FILE, old)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("auto_tagger")

# ============================================================================
# REGEX PRECOMPILATION
# ============================================================================

def compile_rules(rules):
    compiled = []
    for rule in rules:
        compiled.append({
            **rule,
            "patterns":         [re.compile(p) for p in rule["patterns"]],
            "exclude_patterns": [re.compile(p) for p in rule["exclude_patterns"]],
        })
    return compiled


COMPILED_RULES = compile_rules(RULES)


def matches_pattern(text, patterns):
    return any(p.search(text) for p in patterns)

# ============================================================================
# TAG DETERMINATION
# ============================================================================

def determine_tag(torrent_name):
    for rule in COMPILED_RULES:
        if not rule["enabled"]:
            continue
        if rule["exclude_patterns"] and matches_pattern(torrent_name, rule["exclude_patterns"]):
            continue
        if not rule["patterns"]:
            return rule["tag"]
        if matches_pattern(torrent_name, rule["patterns"]):
            return rule["tag"]
    return None

# ============================================================================
# DISCORD NOTIFICATION
# ============================================================================

def notify_discord(title, message, color, torrent_name="", info_hash=""):
    """Send a Discord embed notification. No-op if webhook URL is not set."""
    if not DISCORD_WEBHOOK_URL:
        return

    fields = []
    if torrent_name:
        fields.append({"name": "Torrent", "value": torrent_name, "inline": False})
    if info_hash:
        fields.append({"name": "Hash", "value": info_hash[:12], "inline": True})

    payload = json.dumps({
        "embeds": [{
            "title": title,
            "description": message,
            "color": color,
            "fields": fields,
        }]
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("Discord notification failed: %s", e)


def notify_error(message, torrent_name="", info_hash=""):
    notify_discord("Auto-Tagger Error", message, color=15548997,
                   torrent_name=torrent_name, info_hash=info_hash)


def notify_success(message, torrent_name="", info_hash=""):
    notify_discord("Auto-Tagger", message, color=3066993,
                   torrent_name=torrent_name, info_hash=info_hash)

# ============================================================================
# QBITTORRENT API CLIENT (stdlib-only)
# ============================================================================

class QBittorrentAPI:
    def __init__(self, host, username, password):
        self.host     = host.rstrip('/')
        self.username = username
        self.password = password

        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener     = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def _request(self, method, path, data=None, params=None):
        last_error = None

        for attempt in range(HTTP_RETRIES):
            try:
                url = f"{self.host}{path}"
                if params:
                    url += "?" + urllib.parse.urlencode(params)

                encoded = urllib.parse.urlencode(data).encode("utf-8") if data else None
                req     = urllib.request.Request(url, data=encoded, method=method)

                # Referer required by some qBittorrent versions for CSRF protection
                req.add_header("Referer", self.host)
                # Explicitly set Accept-Encoding to avoid the Qt 6.11.0 crash
                # bug triggered by Python urllib's default "identity" value.
                # See: https://github.com/qbittorrent/qBittorrent/issues/24038
                req.add_header("Accept-Encoding", "gzip")

                with self.opener.open(req, timeout=HTTP_TIMEOUT) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return raw.decode("utf-8")

            except (urllib.error.URLError, socket.timeout, OSError) as e:
                last_error = e
                if attempt < HTTP_RETRIES - 1:
                    log.warning("Request failed (attempt %d/%d): %s — retrying in %ds",
                                attempt + 1, HTTP_RETRIES, e, RETRY_DELAY)
                    time.sleep(RETRY_DELAY)

        raise ConnectionError(f"API unreachable after {HTTP_RETRIES} attempts: {last_error}")

    def login(self):
        response = self._request(
            "POST",
            "/api/v2/auth/login",
            data={"username": self.username, "password": self.password}
        )
        if response.strip() != "Ok.":
            raise PermissionError(f"Login rejected: {response.strip()}")

    def get_existing_tags(self, info_hash):
        response = self._request(
            "GET",
            "/api/v2/torrents/info",
            params={"hashes": info_hash}
        )
        torrents = json.loads(response)
        if not torrents:
            return set()
        tags = torrents[0].get("tags", "")
        return set(t.strip() for t in tags.split(",") if t.strip())

    def add_tag(self, info_hash, tag):
        existing = self.get_existing_tags(info_hash)
        if tag in existing:
            log.info("Tag '%s' already present, skipping", tag)
            return False
        self._request(
            "POST",
            "/api/v2/torrents/addTags",
            data={"hashes": info_hash, "tags": tag}
        )
        log.info("Tag '%s' applied", tag)
        return True

# ============================================================================
# ENTRYPOINT
# ============================================================================

def main():
    if len(sys.argv) < 3:
        log.error("Usage: script.py <torrent_name> <info_hash>")
        sys.exit(1)

    torrent_name = sys.argv[1]
    info_hash    = sys.argv[2]

    # Determine tag from name before touching the network
    tag = determine_tag(torrent_name)
    if not tag:
        log.info("No matching rule, exiting | %s", torrent_name)
        sys.exit(0)

    log.info("Torrent: %s", torrent_name)
    log.info("Tag:     %s", tag)

    api = QBittorrentAPI(QBITTORRENT_HOST, QBITTORRENT_USERNAME, QBITTORRENT_PASSWORD)

    try:
        api.login()
    except ConnectionError as e:
        # Web UI unavailable — exit cleanly so we don't linger or crash qBit
        log.warning("Web UI unavailable, exiting cleanly: %s", e)
        sys.exit(0)
    except PermissionError as e:
        log.error("Login failed: %s", e)
        notify_error(f"Login failed: {e}", torrent_name, info_hash)
        sys.exit(1)

    try:
        api.add_tag(info_hash, tag)
    except ConnectionError as e:
        log.error("Failed to apply tag: %s", e)
        notify_error(f"Failed to apply tag '{tag}': {e}", torrent_name, info_hash)
        sys.exit(0)


if __name__ == "__main__":
    main()