#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
meta_scan_en.py — OSINT for Facebook via RapidAPI (English translation + auto-open links)
Author: Translated & adapted from original (HackUnderway)
Features added:
- Keeps .env usage for API keys (no hardcoding)
- requests.Session with retries + backoff
- Configurable timeouts via CLI (fixed argparse names)
- Flags to skip "premium" endpoints
- Clear error handling
- Automatically opens provided Telegram and website links after run (can disable with --no-open)
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
# Endpoint constants (same as original)
# -----------------------------
PROFILE_HOST = "facebook-pages-scraper3.p.rapidapi.com"
PROFILE_PATH = "/get-profile-home-page-details"   # accepts urlSupplier or url

PAGE_HOST = "social-media-scrape.p.rapidapi.com"
PAGE_DETAILS_PATH = "/get_facebook_pages_details"   # param: link
POSTS_DETAILS_PATH = "/get_facebook_posts_details"  # param: link

# Network settings
DEFAULT_TIMEOUT: Tuple[int, int] = (15, 45)  # (connect, read) seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.6


# -----------------------------
# Networking / session utilities
# -----------------------------
def build_session() -> requests.Session:
    """Create a requests Session with retry/backoff and a custom User-Agent."""
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
    session.headers.update({"User-Agent": "meta-scan/1.0 (+https://github.com/HackUnderway/meta_scan)"})
    return session


def get_env_keys() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Load keys from .env:
    - RAPIDAPI_KEY (common)
    - RAPIDAPI_KEY_FB_SCRAPER3 (optional)
    - RAPIDAPI_KEY_SOCIAL_SCRAPE (optional)
    """
    load_dotenv()
    common = os.getenv("RAPIDAPI_KEY")
    fb_key = os.getenv("RAPIDAPI_KEY_FB_SCRAPER3", None)
    social_key = os.getenv("RAPIDAPI_KEY_SOCIAL_SCRAPE", None)
    if not common and not (fb_key or social_key):
        raise RuntimeError(
            "No RAPIDAPI_KEY found in .env (or RAPIDAPI_KEY_FB_SCRAPER3 / RAPIDAPI_KEY_SOCIAL_SCRAPE)."
        )
    return common or "", fb_key, social_key


def choose_key(common: str, specific: Optional[str]) -> str:
    """Use specific key if available, otherwise use the common key."""
    return specific.strip() if (specific and specific.strip()) else common


def rapidapi_get(
    session: requests.Session,
    host: str,
    path: str,
    params: Dict[str, Any],
    api_key: str,
    timeout: Tuple[int, int] = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """GET to a RapidAPI host with error handling and strict JSON parsing."""
    url = f"https://{host}{path}"
    headers = {
        "x-rapidapi-host": host,
        "x-rapidapi-key": api_key,
    }

    try:
        resp = session.get(url, headers=headers, params=params, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        raise RuntimeError(
            f"Connection timeout connecting to {host}. Try raising --connect-timeout or check your network/VPN/proxy."
        )
    except requests.exceptions.ReadTimeout:
        raise RuntimeError(
            f"Read timeout reading response from {host}. Try raising --read-timeout."
        )
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to {host}: {e}. Possible causes: provider down, network/ISP blocks, VPN/Proxy, or port 443 filtered."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error querying {host}{path}: {e}")

    if not resp.ok:
        try:
            payload = resp.json()
        except Exception:
            payload = {"error": (resp.text or "")[:300]}
        raise RuntimeError(
            f"HTTP {resp.status_code} from {host}{path}. Details: {json.dumps(payload, ensure_ascii=False)}"
        )

    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(
            f"Response from {host}{path} is not valid JSON: {(resp.text or '')[:300]}"
        )


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
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦🟦🟦🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜⬜🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦⬜⬜⬜⬜🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Fore.BLUE + "   🟦🟦🟦🟦🟦⬜⬜🟦🟦")
    print(Back.GREEN + Fore.BLACK + "  By darkboss1bd  ")
    print(Fore.CYAN + f"  Telegram: {TELEGRAM_LINK}")
    print(Fore.CYAN + f"  Website:  {WEBSITE_LINK}")


def show_profile(profile: Dict[str, Any]):
    print(Fore.GREEN + "\nProfile details:\n")
    print(Fore.YELLOW + f"ID: {profile.get('id', 'N/A')}")
    print(Fore.YELLOW + f"Type: {profile.get('type_name', profile.get('type', 'N/A'))}")
    print(Fore.YELLOW + f"Name: {profile.get('name', 'N/A')}")
    print(Fore.YELLOW + f"Gender: {profile.get('gender', 'N/A')}")
    print(Fore.YELLOW + f"Profile picture: {profile.get('profile_picture', 'N/A')}")
    print(Fore.YELLOW + f"Cover photo: {profile.get('cover_photo', 'N/A')}\n")

    intro_cards = profile.get('INTRO_CARDS') or profile.get('intro_cards') or {}
    if isinstance(intro_cards, dict) and intro_cards:
        print(Fore.YELLOW + "Additional details:")
        for key, value in intro_cards.items():
            k = str(key).replace('INTRO_CARD_', '').replace('_', ' ').title()
            print(Fore.YELLOW + f" - {k}: {value}")

    photos = profile.get('PHOTOS') or profile.get('photos')
    if isinstance(photos, list) and photos:
        print(Fore.YELLOW + "\nPhotos:")
        for p in photos[:20]:
            uri = p.get('uri') or p.get('url') or 'N/A'
            pid = p.get('id', 'N/A')
            print(Fore.YELLOW + f" - {uri} (ID: {pid})")


def show_page(page_info: Dict[str, Any]):
    print(Fore.GREEN + "\nPage details:\n")
    print(Fore.YELLOW + f"Title: {page_info.get('title', 'N/A')}")
    print(Fore.YELLOW + f"Description: {page_info.get('description', 'N/A')}")
    print(Fore.YELLOW + f"Image: {page_info.get('image', 'N/A')}")
    print(Fore.YELLOW + f"URL: {page_info.get('url', 'N/A')}")
    print(Fore.YELLOW + f"User ID: {page_info.get('user_id', 'N/A')}")
    print(Fore.YELLOW + f"Redirected to: {page_info.get('redirected_url', 'N/A')}\n")


def show_posts(posts_data: Dict[str, Any]):
    posts = (((posts_data or {}).get('data') or {}).get('posts')) or []
    if not posts:
        print(Fore.RED + "\nNo posts found (or your plan doesn't include them).")
        return

    print(Fore.GREEN + "\nPosts details:\n")
    for post in posts:
        details = post.get('details', {})
        reactions = post.get('reactions', {})
        values = post.get('values', {})

        print(Fore.YELLOW + f"Post ID: {details.get('post_id', 'N/A')}")
        print(Fore.YELLOW + f"Text: {values.get('text', 'N/A')}")
        print(Fore.YELLOW + f"Total reactions: {reactions.get('total_reaction_count', 'N/A')}")
        print(Fore.YELLOW + f"Comments: {details.get('comments_count', 'N/A')}")
        print(Fore.YELLOW + f"Shares: {details.get('share_count', 'N/A')}\n")

        attachments = post.get('attachments') or []
        for att in attachments:
            t = att.get('__typename')
            if t == 'Photo':
                img = ((att.get('photo_image') or {}).get('uri')) or 'N/A'
                print(Fore.YELLOW + f" - Image: {img}")


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

        payload = {
            "username": username,
            "profile": profile,
            "page": page,
            "posts": posts,
        }
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
    parser.add_argument("--no-page", action="store_true", help="Do not query page details (premium endpoint).")
    parser.add_argument("--no-posts", action="store_true", help="Do not query posts (premium endpoint).")
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

    # Profile
    try:
        profile = get_profile_details(session, username, choose_key(common, fb_key))
        if profile:
            show_profile(profile)
        else:
            print(Fore.RED + "\nNo profile obtained (empty response).")
    except Exception as e:
        print(Fore.RED + f"\nError getting profile details: {e}")

    # Page (premium)
    if not args.no_page:
        try:
            page = get_page_details(session, username, choose_key(common, social_key))
            if page:
                show_page(page)
            else:
                print(Fore.RED + "\nCould not fetch page details (maybe a premium endpoint).")
        except Exception as e:
            print(Fore.RED + f"\nError getting page details: {e}")
    else:
        print(Fore.YELLOW + "\n[Skipped] Page details via --no-page")

    # Posts (premium)
    if not args.no_posts:
        try:
            posts = get_posts_details(session, username, choose_key(common, social_key))
            if posts:
                show_posts(posts)
            else:
                print(Fore.RED + "\nCould not fetch posts (maybe a premium endpoint).")
        except Exception as e:
            print(Fore.RED + f"\nError getting posts details: {e}")
    else:
        print(Fore.YELLOW + "\n[Skipped] Posts details via --no-posts")

    save_json_if_requested(args.out_json, username, profile, page, posts)

    # Auto-open links (Telegram + Website) unless disabled
    if not args.no_open:
        try:
            print(Fore.CYAN + f"\nOpening Telegram: {TELEGRAM_LINK}")
            webbrowser.open(TELEGRAM_LINK, new=2)  # new=2 => open in new tab if possible
            print(Fore.CYAN + f"Opening Website: {WEBSITE_LINK}")
            webbrowser.open(WEBSITE_LINK, new=2)
        except Exception as e:
            print(Fore.RED + f"Failed to open links: {e}")


if __name__ == "__main__":
    main()
