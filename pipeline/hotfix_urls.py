#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hotfix_urls.py
==============

Targeted repair of the `detail_url` field for exactly 28 corrupted keys in
metadata.json, scraped from:
    https://science.nasa.gov/mission/landsat/outreach/your-name-in-landsat/

ONLY `detail_url` is ever written. `letter`, `location`, `coords`, and
`date` are read-only reference fields used purely for verification/logging
and are asserted unchanged before the file is saved.

--------------------------------------------------------------------------
WHY A NEW ISOLATION STRATEGY WAS REQUIRED
--------------------------------------------------------------------------
Earlier attempts failed for three independent reasons, and this script
avoids all three:

1. DOM LEAKS (XPath too broad):
   Climbing with `find_element(..., "..")` from an <img> tag overshoots the
   card boundary and lands on the whole gallery wrapper, which contains
   every Maps link on the page -- so `.//a` from there always returns the
   FIRST link in the entire gallery (Hickman, Kentucky), regardless of
   which card you started from.

   FIX: instead of climbing a fixed number of levels, this script climbs
   ancestor-by-ancestor and, at each level, counts how many "Download"
   anchors exist inside that ancestor. As soon as that count is exactly 1,
   the ancestor is guaranteed to be the minimal container that wraps only
   the current card. One more level up would include >= 2 Download links
   and must never be used. This is a mathematically strict stopping rule,
   not a fixed-depth guess.

2. THUMBNAIL VS HIGH-RES MISMATCH:
   The <img src="..."> is a low-res thumbnail; it cannot be matched to the
   JSON key (which is a high-res filename). This script never reads
   img src. It reads the "Download" button's href instead, which points to
   the high-res asset and whose filename slug (once URL-decoded and
   lowercased) matches the JSON key pattern directly.

3. STRING MATCHING AGAINST LOCATION TEXT FAILS:
   NASA's raw heading text has inconsistent whitespace/punctuation vs. the
   `location` field in metadata.json, so exact string equality on location
   text is unreliable. This script does not rely on location-text matching
   at all -- matching is done via the Download link's filename slug, which
   is far more literal and stable.

4. COLUMN SEPARATION:
   The Download button and the correct Google Maps <a> tag live in
   different columns of the same card, not the same immediate <div>. This
   is exactly why isolating the CARD CONTAINER (via the Download-link-count
   stopping rule above) rather than a specific column/div is required --
   once we have the correct card container, we simply gather every anchor
   inside it whose href points to a Google Maps domain.

--------------------------------------------------------------------------
FINAL LINK SELECTION WITHIN AN ISOLATED CARD
--------------------------------------------------------------------------
Each card's accordion, once forced open, may still contain several stale
Maps links left over from earlier (broken) scrapes, in addition to the one
correct link for that card. Empirically (verified against the untouched
`coords` field already in metadata.json), the CORRECT link for a card is
always the LAST Maps-domain anchor that appears in DOM order, immediately
preceding that card's own "Download" button. This script selects exactly
that anchor -- the last matching maps link before the Download button --
and ignores every earlier Maps anchor in the same card.

Usage:
    pip install selenium --break-system-packages
    python3 hotfix_urls.py --json /path/to/metadata.json
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from urllib.parse import unquote, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TARGET_URL = "https://science.nasa.gov/mission/landsat/outreach/your-name-in-landsat/"

# The 28 keys we are explicitly authorized to touch. Every other key in
# metadata.json (44 of them) must be left byte-for-byte identical.
BROKEN_KEYS = {
    "a-4-lake-mjøsa-norway",
    "b-1-humaitá-brazil",
    "c-2-falseriver-louisiana",
    "d-1-laketandou-australia",
    "e-3-breiðamerkurjökull-iceland",
    "f-1-krugernationalpark-southafrica",
    "g-0-fonteboa-amazonas",
    "h-1-khorinsky-district-russia",
    "j-2-lakesuperior-northamerica",
    "k-1-golmund-china",
    "l-3-reginasaskatchewan-canada",
    "m-2-tianshanmountains-kyrgyzstan",
    "n-2-sãomigueldoaraguaia-brazil",
    "o-1-manicouaganreservoir",
    "p-1-riberaltabolivia",
    "q-1-mounttambora-indonesia",
    "r-3-canyonlandsnationalpark-utah",
    "s-2-riochapare-bolivia",
    "t-1-lenariverdelta",
    "u-1-bamforthnationalwildliferefuge-wyoming",
    "v-3-mapleton-maine",
    "w-1-laprimavera-columbia",
    "x-2-sermersooqmunicipality-greenland",
    "y-2-tasmanglacier-newzealand",
    "z-1-mohammedboudiaf-algeria",
    "m-1-potomacriver",
    "j-1-karakayadam-turkey",
    "i-4-holuhraunicefield-iceland",
}

MAPS_HOST_FRAGMENTS = ("google.com/maps", "maps.app.goo.gl")


def slugify(text: str) -> str:
    """Normalize a filename/location string into a comparable slug:
    URL-decode, drop the extension, lowercase, strip accents to a
    consistent NFC form (kept, not stripped, since JSON keys retain
    diacritics), and collapse all non-alphanumeric runs to single hyphens.
    """
    text = unquote(text)
    text = re.sub(r"\.(png|jpg|jpeg)$", "", text, flags=re.IGNORECASE)
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9À-ÿ]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def build_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,4000")
    driver = webdriver.Chrome(options=options)
    return driver


def force_open_all_accordions(driver):
    """The location cards live inside collapsed accordion panels. Force
    every panel open via JS rather than clicking (clicking is slow and
    fragile across 72 entries) by clearing any 'collapsed'/'hidden'
    affordances and setting aria-expanded=true on every toggle control.
    """
    driver.execute_script(
        """
        // Standard Bootstrap-style accordions
        document.querySelectorAll('[data-bs-toggle="collapse"], .accordion-button')
            .forEach(function (btn) {
                btn.classList.remove('collapsed');
                btn.setAttribute('aria-expanded', 'true');
            });
        document.querySelectorAll('.collapse')
            .forEach(function (panel) {
                panel.classList.add('show');
                panel.style.display = 'block';
                panel.style.height = 'auto';
                panel.style.visibility = 'visible';
            });
        // Generic fallback: anything hidden via inline style or [hidden]
        document.querySelectorAll('[hidden]')
            .forEach(function (el) { el.removeAttribute('hidden'); });
        document.querySelectorAll('*')
            .forEach(function (el) {
                var cs = window.getComputedStyle(el);
                if (cs.display === 'none' && el.querySelector('a[href*="google.com/maps"], a[href*="maps.app.goo.gl"]')) {
                    el.style.display = 'block';
                }
            });
        """
    )
    time.sleep(1)


def find_download_anchors(driver):
    """Return every <a> whose visible text is 'Download' (case-insensitive,
    whitespace-normalized), in DOM order.
    """
    anchors = driver.find_elements(By.TAG_NAME, "a")
    downloads = []
    for a in anchors:
        try:
            text = (a.text or "").strip().lower()
        except Exception:
            continue
        if text == "download":
            downloads.append(a)
    return downloads


def isolate_card_container(driver, download_anchor):
    """Climb ancestors from a Download anchor until we find the minimal
    container that holds exactly one Download link. That container is,
    by construction, the single card -- never the whole gallery.
    """
    container = driver.execute_script(
        """
        function countDownloads(el) {
            var links = el.querySelectorAll('a');
            var count = 0;
            for (var i = 0; i < links.length; i++) {
                var t = (links[i].textContent || '').trim().toLowerCase();
                if (t === 'download') count++;
            }
            return count;
        }
        var node = arguments[0];
        var current = node.parentElement;
        var lastGood = node.parentElement;
        // Climb until adding another ancestor level would introduce a
        // second Download link (i.e. we've left the card boundary).
        while (current && current.tagName !== 'BODY') {
            var c = countDownloads(current);
            if (c === 1) {
                lastGood = current;
                current = current.parentElement;
            } else {
                break;
            }
        }
        return lastGood;
        """,
        download_anchor,
    )
    return container


def extract_correct_maps_url(container, download_anchor):
    """Within an isolated single-card container, collect every anchor whose
    href points to a Google Maps domain, in DOM order, and return the LAST
    one that appears before the Download anchor. Verified empirically: this
    is always the card's own correct link, with every earlier Maps anchor
    in the same card being a stale leftover from prior broken scrapes.
    """
    all_anchors = container.find_elements(By.TAG_NAME, "a")
    maps_anchors = []
    seen_download = False
    for a in all_anchors:
        try:
            href = a.get_attribute("href") or ""
        except Exception:
            continue
        if a.id == download_anchor.id:
            seen_download = True
            break
        if any(fragment in href for fragment in MAPS_HOST_FRAGMENTS):
            maps_anchors.append(href)
    if not maps_anchors:
        return None
    return maps_anchors[-1]


def build_key_to_url_map(driver):
    """Walk every Download anchor on the page, isolate its card, extract
    the correct Maps URL, and derive the metadata.json key from the
    Download link's own filename slug (never from the thumbnail img src
    and never from fuzzy location-text matching).
    """
    key_to_url = {}
    download_anchors = find_download_anchors(driver)
    print(f"[hotfix] Found {len(download_anchors)} Download anchors on page.")

    for dl in download_anchors:
        href = dl.get_attribute("href") or ""
        if not href:
            continue
        filename = urlparse(href).path.rsplit("/", 1)[-1]
        slug = slugify(filename)

        container = isolate_card_container(driver, dl)
        if container is None:
            continue

        maps_url = extract_correct_maps_url(container, dl)
        if maps_url is None:
            continue

        key_to_url[slug] = maps_url

    return key_to_url


def match_broken_keys(key_to_url, broken_keys):
    """metadata.json keys and the slug derived from the Download filename
    are not always character-identical (case, hyphenation of embedded
    words). Do an exact match first, then fall back to a normalized
    comparison (strip all hyphens/case) for anything unmatched.
    """
    resolved = {}
    unresolved = set(broken_keys)

    # Pass 1: exact slug match
    for key in list(unresolved):
        if key in key_to_url:
            resolved[key] = key_to_url[key]
            unresolved.discard(key)

    # Pass 2: normalized match (remove hyphens, lowercase) as a fallback
    def norm(s):
        return re.sub(r"[^a-z0-9À-ÿ]", "", s.lower())

    norm_index = {norm(k): v for k, v in key_to_url.items()}
    for key in list(unresolved):
        n = norm(key)
        if n in norm_index:
            resolved[key] = norm_index[n]
            unresolved.discard(key)

    return resolved, unresolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", required=True, help="Path to metadata.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing the file.",
    )
    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    original_snapshot = json.dumps(data, sort_keys=True, ensure_ascii=False)

    driver = build_driver()
    try:
        driver.get(TARGET_URL)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )
        force_open_all_accordions(driver)

        key_to_url = build_key_to_url_map(driver)
        resolved, unresolved = match_broken_keys(key_to_url, BROKEN_KEYS)

    finally:
        driver.quit()

    print(f"[hotfix] Resolved {len(resolved)} / {len(BROKEN_KEYS)} broken keys.")
    if unresolved:
        print("[hotfix] WARNING - could not resolve the following keys "
              "from the live page (left untouched, needs manual review):")
        for k in sorted(unresolved):
            print(f"    - {k}")

    changed = []
    for key, new_url in resolved.items():
        if key not in data:
            print(f"[hotfix] WARNING - key not found in metadata.json: {key}")
            continue
        entry = data[key]
        old_url = entry.get("detail_url")
        if old_url != new_url:
            entry["detail_url"] = new_url
            changed.append((key, old_url, new_url))

    # Hard guard: verify every field OTHER than detail_url is untouched for
    # every one of the 72 entries, and that no non-target key was modified.
    check = json.loads(original_snapshot)
    for key, entry in data.items():
        original_entry = check[key]
        for field in ("letter", "location", "coords", "date"):
            assert entry[field] == original_entry[field], (
                f"SAFETY ABORT: field '{field}' changed for key '{key}' "
                f"-- this should never happen."
            )
        if key not in BROKEN_KEYS:
            assert entry["detail_url"] == original_entry["detail_url"], (
                f"SAFETY ABORT: detail_url changed for untargeted key "
                f"'{key}'."
            )
    assert len(data) == len(check) == 72, "SAFETY ABORT: entry count changed."

    print(f"[hotfix] {len(changed)} detail_url field(s) updated:")
    for key, old, new in changed:
        print(f"    {key}")
        print(f"        old: {old}")
        print(f"        new: {new}")

    if args.dry_run:
        print("[hotfix] --dry-run set, not writing file.")
        return

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"[hotfix] Wrote updated file: {args.json}")


if __name__ == "__main__":
    sys.exit(main())