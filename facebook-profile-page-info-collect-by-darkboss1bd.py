#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
facebook-profile-page-info-collect-by-darkboss1bd.py — OSINT for Facebook via RapidAPI (modified for free-plan default)
By darkboss1bd — updated to skip premium endpoints by default and give clear guidance on 403.
"""
import os
import sys
import json
import argparse
from typing import Any, Dict, Optional, Tuple
import webbrowser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import colorama
from colorama import Fore, Back

# -----------------------------
# User links (inserted as requested)
# -----------------------------
TELEGRAM_LINK = "https://t.me/darkvaiadmin"
WEBSITE_LINK = "https://serialkey.top/"

# -----------------------------
# Endpoint constants (same as original defaults)
# Note: profile endpoint may be premium on some subscriptions.
# We keep original hosts but script will skip premium endpoints by default.
# -----------------------------
PROFILE_HOST = "facebook-pages-scraper3.p.rapidapi.com"
PROFILE_PATH = "/get-profile-home-page-details"

PAGE_HOST = "social-media-scrape.p.rapidapi.com"
PAGE_DETAILS_PATH = "/get_facebook_pages_details"
POSTS_DETAILS_PATH = "/get_facebook_posts_details"

# Network settings
DEFAULT_TIMEOUT: Tuple[int, int] = (15, 45)  # (connect, read) seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.6


# -----------------------------
# Networking / session utilities
# -----------------------------
def build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "meta-scan/1.0 (+https://github.com/darkboss1bd/facebook-profile-page-info-collect-by-darkboss1bd.git)"})
    return session


def get_env_keys() -> Tuple[str, Optional[str], Optional[str]]:
    load_dotenv()
    common = os.getenv("RAPIDAPI_KEY")
    fb_key = os.getenv("RAPIDAPI_KEY_FB_SCRAPER3", None)
    social_key = os.getenv("RAPIDAPI_KEY_SOCIAL_SCRAPE", None)
    if not common and not (fb_key or social_key):
        raise RuntimeError(
            "No RAPIDAPI_KEY found in .env (or RAPIDAPI_KEY_FB_SCRAPER3 / RAPIDAPI_KEY_SOCIAL_SCRAPE). "
            "Create a .env file with: RAPIDAPI_KEY=your_key"
        )
    return common or "", fb_key, social_key


def choose_key(common: str, specific: Optional[str]) -> str:
    return specific.strip() if (specific and specific.strip()) else common


def rapidapi_get(
    session: requests.Session,
    host: str,
    path: str,
    params: Dict[str, Any],
    api_key: str,
    timeout: Tuple[int, int] = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    url = f"https://{host}{path}"
    headers = {
        "x-rapidapi-host": host,
        "x-rapidapi-key": api_key,
    }

    try:
        resp = session.get(url, headers=headers, params=params, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        raise RuntimeError(f"Connection timeout connecting to {host}.")
    except requests.exceptions.ReadTimeout:
        raise RuntimeError(f"Read timeout reading response from {host}.")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Could not connect to {host}: {e}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error querying {host}{path}: {e}")

    # If 403 with "not subscribed" return special error for nicer messaging
    if resp.status_code == 403:
        # try to parse json body
        msg = ""
        try:
            j = resp.json()
            msg = j.get("message") or j.get("error") or json.dumps(j, ensure_ascii=False)
        except Exception:
            msg = resp.text or "Forbidden (HTTP 403)"
        # Normalize check
        if "not subscribed" in msg.lower() or "not subscribed to this api" in msg.lower():
            raise RuntimeError(f"HTTP 403 from {host}{path}. Details: {json.dumps({'message': msg}, ensure_ascii=False)}")
        # otherwise generic 403
        raise RuntimeError(f"HTTP 403 from {host}{path}. Details: {msg}")

    if not resp.ok:
        try:
            payload = resp.json()
        except Exception:
            payload = {"error": (resp.text or "")[:300]}
        raise RuntimeError(f"HTTP {resp.status_code} from {host}{path}. Details: {json.dumps(payload, ensure_ascii=False)}")

    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(f"Response from {host}{path} is not valid JSON: {(resp.text or '')[:300]}")


# -----------------------------
# Business logic functions
# -----------------------------
def get_profile_details(session: requests.Session, username: str, api_key: str) -> Optional[Dict[str, Any]]:
    fb_url = f"https://www.facebook.com/{username}"
    params = {"urlSupplier": fb_url, "url": fb_url}
    data = rapidapi_get(session, PROFILE_HOST, PROFILE_PATH, params, api_key)
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data if isinstance(data, dict) else None


def get_page_details(session: requests.Session, username: str, api_key: str) -> Optional[Dict[str, Any]]:
    fb_url = f"https://www.facebook.com/{username}"
    params = {"link": fb_url}
    data = rapidapi_get(session, PAGE_HOST, PAGE_DETAILS_PATH, params, api_key)
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return None


def get_posts_details(session: requests.Session, username: str, api_key: str) -> Optional[Dict[str, Any]]:
    fb_url = f"https://www.facebook.com/{username}"
    params = {"link": fb_url}
    data = rapidapi_get(session, PAGE_HOST, POSTS_DETAILS_PATH, params, api_key)
    if isinstance(data, dict) and "data" in data:
        return data
    if isinstance(data, list):
        return {"data": {"posts": data}}
    return None


# -----------------------------
# Console presentation
# -----------------------------
def print_banner():
    colorama.init(autoreset=True)
    print(Fore.CYAN + "Meta-scan (free-plan default) — darkboss1bd")
    print(Fore.CYAN + f"Telegram: {TELEGRAM_LINK}   Website: {WEBSITE_LINK}")


def show_profile(profile: Dict[str, Any]):
    print(Fore.GREEN + "\nProfile details:\n")
    print(Fore.YELLOW + f"Name: {profile.get('name', 'N/A')}")
    print(Fore.YELLOW + f"Profile picture: {profile.get('profile_picture', 'N/A')}")
    # minimal printing to avoid over-clutter
    for k in ("id", "type", "about", "gender"):
        if profile.get(k):
            print(Fore.YELLOW + f"{k.title()}: {profile.get(k)}")


def show_page(page_info: Dict[str, Any]):
    print(Fore.GREEN + "\nPage details:\n")
    print(Fore.YELLOW + f"Title: {page_info.get('title', 'N/A')}")
    print(Fore.YELLOW + f"URL: {page_info.get('url', 'N/A')}")


def show_posts(posts_data: Dict[str, Any]):
    posts = (((posts_data or {}).get('data') or {}).get('posts')) or []
    if not posts:
        print(Fore.RED + "\nNo posts found (or your plan doesn't include them).")
        return
    print(Fore.GREEN + "\nPosts details (first 5):\n")
    for post in posts[:5]:
        print(Fore.YELLOW + f"- {post.get('values', {}).get('text', '(no text)')[:200]}")


# -----------------------------
# Optional JSON save
# -----------------------------
def save_json_if_requested(out_dir: Optional[str], username: str,
                           profile: Optional[Dict[str, Any]],
                           page: Optional[Dict[str, Any]],
                           posts: Optional[Dict[str, Any]]) -> None:
    if not out_dir:
        return
    try:
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.join(out_dir, username.replace("/", "_") or "output")
        payload = {"username": username, "profile": profile, "page": page, "posts": posts}
        out_path = f"{base}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(Fore.CYAN + f"\n[✔] Saved JSON: {out_path}")
    except Exception as e:
        print(Fore.RED + f"\n[!] Error saving JSON: {e}")


# -----------------------------
# Main / CLI
# -----------------------------
def main():
    print_banner()

    parser = argparse.ArgumentParser(description="Meta Scan OSINT for Facebook (RapidAPI)")
    parser.add_argument("-u", "--username", help="Facebook username/permalink (e.g., nasa)")
    # NOTE: changed behavior — by default we SKIP premium endpoints.
    parser.add_argument("--include-page", action="store_true", help="Include page details (premium endpoint). Opt-in ONLY.")
    parser.add_argument("--include-posts", action="store_true", help="Include posts details (premium endpoint). Opt-in ONLY.")
    parser.add_argument("--connect-timeout", type=int, default=15, dest="connect_timeout", help="Connection timeout in seconds.")
    parser.add_argument("--read-timeout", type=int, default=45, dest="read_timeout", help="Read timeout in seconds.")
    parser.add_argument("--out-json", help="Directory to save combined output as JSON (e.g., ./out).")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open Telegram/Website links after run.")
    args = parser.parse_args()

    global DEFAULT_TIMEOUT
    DEFAULT_TIMEOUT = (args.connect_timeout, args.read_timeout)

    username = args.username or input(Fore.RED + "\n[*] Enter the username: ").strip()
    if not username:
        print(Fore.RED + "Empty username. Exiting.")
        sys.exit(1)

    try:
        common, fb_key, social_key = get_env_keys()
    except Exception as e:
        print(Fore.RED + f"[Config] {e}")
        sys.exit(1)

    session = build_session()

    profile = None
    page = None
    posts = None

    # PROFILE (we try profile call — if it gives 403 "not subscribed", we explain steps)
    try:
        key_for_profile = choose_key(common, fb_key)
        profile = get_profile_details(session, username, key_for_profile)
        if profile:
            show_profile(profile)
        else:
            print(Fore.RED + "\nNo profile obtained (empty response).")
    except Exception as e:
        err = str(e)
        print(Fore.RED + f"\nError getting profile details: {err}")
        if "not subscribed" in err.lower() or "not subscribed to this api" in err.lower():
            print(Fore.YELLOW + "\nIt looks like your RapidAPI plan does not include this profile endpoint.")
            print(Fore.YELLOW + "Options:")
            print(Fore.YELLOW + "  1) Use a different endpoint/provider you subscribed to.")
            print(Fore.YELLOW + "  2) Skip premium endpoints entirely (this script already skips page/posts by default).")
            print(Fore.YELLOW + "  3) If you have another RapidAPI key for a provider, set RAPIDAPI_KEY_SOCIAL_SCRAPE in your .env and re-run.")
            # continue without aborting — free-plan fallback behavior
        # continue execution to try non-premium paths (if any)

    # PAGE (premium) — only if user explicitly asked via --include-page
    if args.include_page:
        try:
            page = get_page_details(session, username, choose_key(common, social_key))
            if page:
                show_page(page)
            else:
                print(Fore.RED + "\nCould not fetch page details (empty).")
        except Exception as e:
            err = str(e)
            print(Fore.RED + f"\nError getting page details: {err}")
            if "not subscribed" in err.lower():
                print(Fore.YELLOW + "Page endpoint appears premium and your subscription doesn't include it. Try running without --include-page.")
    else:
        print(Fore.CYAN + "\n[Info] Skipped page details (premium) — use --include-page to opt-in.")

    # POSTS (premium) — only if user explicitly asked via --include-posts
    if args.include_posts:
        try:
            posts = get_posts_details(session, username, choose_key(common, social_key))
            if posts:
                show_posts(posts)
            else:
                print(Fore.RED + "\nCould not fetch posts (empty).")
        except Exception as e:
            err = str(e)
            print(Fore.RED + f"\nError getting posts details: {err}")
            if "not subscribed" in err.lower():
                print(Fore.YELLOW + "Posts endpoint appears premium and your subscription doesn't include it. Try running without --include-posts.")
    else:
        print(Fore.CYAN + "\n[Info] Skipped posts details (premium) — use --include-posts to opt-in.")

    save_json_if_requested(args.out_json, username, profile, page, posts)

    if not args.no_open:
        try:
            print(Fore.CYAN + f"\nOpening Telegram: {TELEGRAM_LINK}")
            webbrowser.open(TELEGRAM_LINK, new=2)
            print(Fore.CYAN + f"Opening Website: {WEBSITE_LINK}")
            webbrowser.open(WEBSITE_LINK, new=2)
        except Exception as e:
            print(Fore.RED + f"Failed to open links: {e}")


if __name__ == "__main__":
    main()
