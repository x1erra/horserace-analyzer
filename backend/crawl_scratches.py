
import logging
import time
import os
import re
import shutil
import subprocess
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from email.utils import parsedate_to_datetime
from supabase_client import get_supabase_client
from crawl_equibase import (
    COMMON_TRACKS,
    DEFAULT_BROWSER_HEADERS,
    create_equibase_webdriver,
    normalize_name,
    normalize_pgm,
    page_looks_like_imperva,
    warm_equibase_browser_session,
)

try:
    import cloudscraper
except ImportError:  # pragma: no cover - installed in production image
    cloudscraper = None

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - installed in some environments only
    curl_requests = None

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - installed in scheduler image
    PlaywrightTimeoutError = Exception
    sync_playwright = None

# Configure logging
logger = logging.getLogger(__name__)

# NOTE: Equibase also provides RSS feeds for late changes which are structured in XML.
# URL: https://www.equibase.com/premium/eqbLateChangeRSS.cfm
# Example Feed: https://www.equibase.com/static/latechanges/rss/AQU-USA.rss
# While structured, the <description> field bundles multiple changes (including cancellations)
# into a single HTML text block that requires regex parsing.
# The current HTML scraper used in this file is preferred for its granular row-based structure,
# but the RSS feed remains a viable "break-glass" fallback if the HTML layout changes drastically.


EQUIBASE_BASE_URL = "https://www.equibase.com/static/latechanges/html/"
LATE_CHANGES_INDEX_URL = "https://www.equibase.com/static/latechanges/html/latechanges.html"
TVG_LATE_CHANGES_TRACK_URL = "https://tvg.equibase.com/static/latechanges/html/latechanges{track_code}-USA.html"
LEGACY_LATE_CHANGES_TRACK_URL = "https://www.equibase.com/static/latechanges/html/latechanges{track_code}-USA.html"
MOBILE_LATE_CHANGES_TRACK_URL = "https://mobile.equibase.com/html/scratches{track_code}.html"

SCRATCH_PAGE_HEADERS = {
    **DEFAULT_BROWSER_HEADERS,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def _html_response_is_usable(text):
    return bool(text) and len(text) > 500 and not page_looks_like_imperva(text)


def _fetcher_chain():
    return (
        ("requests", fetch_page_via_requests),
        ("cloudscraper", fetch_page_via_cloudscraper),
        ("curl_cffi", fetch_page_via_curl_cffi),
        ("powershell", fetch_page_via_powershell),
        ("selenium", fetch_page_via_selenium),
        ("playwright", fetch_page_via_playwright),
    )


def _update_fetch_telemetry(telemetry, fetcher_name, success):
    if telemetry is None:
        return
    attempts = telemetry.setdefault("attempts_by_fetcher", {})
    attempts[fetcher_name] = attempts.get(fetcher_name, 0) + 1

    if success:
        successes = telemetry.setdefault("successes_by_fetcher", {})
        successes[fetcher_name] = successes.get(fetcher_name, 0) + 1
        telemetry["successful_fetcher"] = fetcher_name


def _merge_fetch_telemetry(target, source):
    if target is None or not source:
        return

    for key in ("attempts_by_fetcher", "successes_by_fetcher"):
        source_map = source.get(key, {})
        if not source_map:
            continue
        target_map = target.setdefault(key, {})
        for fetcher_name, count in source_map.items():
            target_map[fetcher_name] = target_map.get(fetcher_name, 0) + count


def _format_fetcher_label(telemetry):
    if not telemetry:
        return "unknown fetcher"
    return telemetry.get("successful_fetcher") or "unknown fetcher"


def _summarize_contributions(source_counts):
    ordered_keys = ("rss", "direct_html", "mobile_html", "index_html", "otb")
    return ", ".join(f"{key}={source_counts.get(key, 0)}" for key in ordered_keys)


def _summarize_fetchers(fetch_telemetry):
    successes = (fetch_telemetry or {}).get("successes_by_fetcher", {})
    if not successes:
        return "none"
    order = ("requests", "cloudscraper", "curl_cffi", "powershell", "selenium", "playwright")
    parts = [f"{name}={successes[name]}" for name in order if successes.get(name)]
    return ", ".join(parts) if parts else "none"


def _discover_chromium_binary():
    explicit = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if explicit and os.path.exists(explicit):
        return explicit
    for binary in ('/usr/bin/chromium', '/usr/bin/chromium-browser'):
        if os.path.exists(binary):
            return binary
    return None


def fetch_page_via_requests(url, timeout=15):
    try:
        response = requests.get(url, headers=SCRATCH_PAGE_HEADERS, timeout=timeout)
        if response.status_code == 200 and _html_response_is_usable(response.text):
            return response.text
        logger.warning("requests fetch failed for %s with status %s", url, response.status_code)
    except requests.exceptions.Timeout:
        logger.warning("requests timed out for %s", url)
    except Exception as exc:
        logger.warning("requests fetch failed for %s: %s", url, exc)
    return None


def fetch_page_via_cloudscraper(url, timeout=20):
    if cloudscraper is None:
        return None
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=SCRATCH_PAGE_HEADERS, timeout=timeout)
        if response.status_code == 200 and _html_response_is_usable(response.text):
            return response.text
        logger.warning("cloudscraper fetch failed for %s with status %s", url, response.status_code)
    except Exception as exc:
        logger.warning("cloudscraper fetch failed for %s: %s", url, exc)
    return None


def fetch_page_via_curl_cffi(url, timeout=20):
    if curl_requests is None:
        return None
    try:
        response = curl_requests.get(
            url,
            headers=SCRATCH_PAGE_HEADERS,
            impersonate='chrome',
            timeout=timeout,
        )
        if response.status_code == 200 and _html_response_is_usable(response.text):
            return response.text
        logger.warning("curl_cffi fetch failed for %s with status %s", url, response.status_code)
    except Exception as exc:
        logger.warning("curl_cffi fetch failed for %s: %s", url, exc)
    return None


def fetch_page_via_powershell(url, timeout=20):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        return None

    temp_file = f"/tmp/equibase_scratches_{int(time.time())}_{os.getpid()}.html"
    script = (
        "$ProgressPreference='SilentlyContinue'; "
        f"$headers=@{{'User-Agent'='{SCRATCH_PAGE_HEADERS['User-Agent']}';'Accept'='{SCRATCH_PAGE_HEADERS['Accept']}';'Referer'='{SCRATCH_PAGE_HEADERS['Referer']}'}}; "
        f"Invoke-WebRequest -Uri '{url}' -Headers $headers -OutFile '{temp_file}' -TimeoutSec {timeout}"
    )

    try:
        result = subprocess.run(
            [shell, "-NoLogo", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("PowerShell fetch failed for %s: %s", url, result.stderr.strip())
            return None
        if not os.path.exists(temp_file):
            logger.warning("PowerShell did not produce a file for %s", url)
            return None
        with open(temp_file, 'r', encoding='utf-8', errors='ignore') as handle:
            content = handle.read()
        if _html_response_is_usable(content):
            return content
        logger.warning("PowerShell returned unusable content for %s", url)
    except Exception as exc:
        logger.warning("PowerShell fetch failed for %s: %s", url, exc)
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
    return None


def fetch_page_via_selenium(url, timeout=45):
    driver = None
    try:
        driver = create_equibase_webdriver(timeout=timeout)
        if driver is None:
            return None
        ready = warm_equibase_browser_session(driver, url, min(timeout, 30))
        html = driver.page_source or ""
        if ready and _html_response_is_usable(html):
            return html
        logger.warning("selenium returned unusable content for %s", url)
    except Exception as exc:
        logger.warning("selenium fetch failed for %s: %s", url, exc)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return None


def fetch_page_via_playwright(url, timeout=45):
    if sync_playwright is None:
        return None

    chromium_binary = _discover_chromium_binary()
    launch_options = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1400,1200",
        ],
    }
    if chromium_binary:
        launch_options["executable_path"] = chromium_binary

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(
                user_agent=SCRATCH_PAGE_HEADERS["User-Agent"],
                extra_http_headers={
                    "Accept": SCRATCH_PAGE_HEADERS["Accept"],
                    "Accept-Language": SCRATCH_PAGE_HEADERS["Accept-Language"],
                    "Referer": SCRATCH_PAGE_HEADERS["Referer"],
                },
                viewport={"width": 1400, "height": 1200},
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            deadline = time.time() + timeout
            while time.time() < deadline:
                html = page.content()
                if _html_response_is_usable(html):
                    browser.close()
                    return html
                page.wait_for_timeout(1000)
            browser.close()
            logger.warning("Playwright remained blocked or empty for %s", url)
    except PlaywrightTimeoutError:
        logger.warning("Playwright timed out for %s", url)
    except Exception as exc:
        logger.warning("Playwright fetch failed for %s: %s", url, exc)
    return None


def fetch_static_page(url, retries=2, telemetry=None):
    """
    Fetch a late-changes HTML page using layered HTTP and browser fallbacks.
    """
    for attempt in range(retries):
        for fetcher_name, fetcher in _fetcher_chain():
            html = fetcher(url)
            _update_fetch_telemetry(telemetry, fetcher_name, bool(html))
            if html:
                return html
        if attempt < retries - 1:
            time.sleep(1)

    logger.error(f"All fetch methods failed for {url}")
    return None

def parse_late_changes_index(telemetry=None):
    """
    Parse the main late changes page to find links for specific tracks
    Returns: List of dicts { 'track_code': 'GP', 'url': '...' }
    """
    html = fetch_static_page(LATE_CHANGES_INDEX_URL, telemetry=telemetry)
    if not html:
        logger.error("Failed to fetch Late Changes index")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Links are usually in a list or table. 
    # Example href: "latechangesGP-USA.html"
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'latechanges' in href and '-USA.html' in href:
            # Extract track code: latechangesGP-USA.html -> GP
            match = re.search(r'latechanges([A-Z0-9]+)-USA\.html', href)
            if match:
                code = match.group(1)
                full_url = EQUIBASE_BASE_URL + href if not href.startswith('http') else href
                links.append({'track_code': code, 'url': full_url})
                
    return links


def fetch_direct_track_changes_page(track_code, telemetry=None):
    """
    Fetch a late-changes page directly for a specific track code.
    This avoids relying on the legacy index page to enumerate available tracks.

    Returns: tuple[str|None, str|None] => (html, source_url)
    """
    for template in (TVG_LATE_CHANGES_TRACK_URL, LEGACY_LATE_CHANGES_TRACK_URL):
        url = template.format(track_code=track_code)
        html = fetch_static_page(url, telemetry=telemetry)
        if html:
            return html, url
    return None, None


def fetch_mobile_track_changes_page(track_code, telemetry=None):
    url = MOBILE_LATE_CHANGES_TRACK_URL.format(track_code=track_code)
    html = fetch_static_page(url, telemetry=telemetry)
    if html:
        return html, url
    return None, None


def parse_mobile_track_changes(html, track_code):
    """
    Parse Equibase mobile scratches/changes pages as a last-ditch fallback.
    These pages are simpler and often survive when other late-changes paths do not.
    """
    if not html:
        return []

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if "TODAY'S SCRATCHES AND CHANGES" not in text.upper():
        logger.warning(f"Unexpected mobile late-changes page format for {track_code}")
        return []

    changes = []
    race_blocks = re.finditer(
        r'<table[^>]*bgcolor="#008000"[^>]*>.*?<b>Race\s+(\d+)</b>.*?</table>(.*?)(?=<table[^>]*bgcolor="#008000"[^>]*>.*?<b>Race\s+\d+</b>|$)',
        html,
        re.IGNORECASE | re.DOTALL,
    )

    for match in race_blocks:
        race_number = int(match.group(1))
        block = match.group(2)
        item_matches = re.finditer(
            r'(?:<p>\s*<b>#\s*([^<:\s]+)\s+(.+?):\s*</b>\s*</p>\s*)?<p>\s*<ChangeDescWeb>\s*(.*?)\s*</ChangeDescWeb>\s*</p>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        for item in item_matches:
            program_number = normalize_pgm(item.group(1)) if item.group(1) else None
            horse_name = normalize_name(item.group(2)) if item.group(2) else ""
            description = BeautifulSoup(item.group(3), "html.parser").get_text(" ", strip=True)
            description = normalize_change_description(description)
            if not description:
                continue
            changes.append({
                "race_number": race_number,
                "program_number": program_number,
                "horse_name": horse_name,
                "change_type": determine_change_type(description),
                "description": description,
            })

    return changes

def determine_change_type(description):
    """
    Determine the type of change based on the description text
    """
    desc_lower = description.lower()
    
    if 'scratched' in desc_lower:
        return 'Scratch'
    elif 'jockey' in desc_lower:
        return 'Jockey Change'
    elif 'weight' in desc_lower:
        return 'Weight Change'
    elif 'blinker' in desc_lower or 'equipment' in desc_lower:
        return 'Equipment Change'
    elif 'first start since reported as' in desc_lower or 'reported as gelding' in desc_lower:
        return 'Horse Note'
    elif 'cancel' in desc_lower:
        # Use centralized validation to avoid false positives (e.g. Wagering cancelled)
        if is_valid_cancellation(description):
            return 'Race Cancelled'
            
        if 'wagering' in desc_lower or 'pool' in desc_lower:
            return 'Wagering' # New type, or return 'Other' if we don't want to track it
            
        return 'Other'
    
    return 'Other'


def normalize_change_description(description):
    """Clean Equibase late-change descriptions into a stable, human-readable form."""
    if not description:
        return ""

    description = re.sub(r"\s+", " ", description).strip()
    description = re.sub(r"\s*;\s*", "; ", description)
    description = re.sub(r"\s*-\s+", " - ", description)

    parts = []
    seen = set()
    for raw_part in [part.strip() for part in description.split(";") if part.strip()]:
        cleaned_part = re.sub(r"\s+-\s+[YN]$", "", raw_part, flags=re.IGNORECASE).strip()
        canonical = cleaned_part.lower()
        if canonical in seen:
            continue
        seen.add(canonical)
        parts.append(cleaned_part)

    return "; ".join(parts)

def is_valid_cancellation(text):
    """
    Centralized validation for race cancellations.
    Returns True if this is a legitimate race cancellation, False if it's wagering or other noise.
    """
    if not text: return False
    text_lower = text.lower()
    
    if 'cancel' not in text_lower:
        return False
        
    # EXCLUSION LIST
    # 'wagering' -> "Show Wagering Cancelled"
    # 'simulcast' -> "Simulcast Cancelled"
    # 'turf' -> "Turf Racing Cancelled"
    # 'superfecta', 'trifecta', etc are covered by 'wagering' usually, but generic filtering is safer
    
    exclusion_keywords = [
        'wagering', 'simulcast', 'pool', 'turf racing', 
        'superfecta', 'trifecta', 'exacta', 'daily double', 'pick', 'quinella',
        'win', 'place', 'show', 'omnibus'
    ]
    
    if any(k in text_lower for k in exclusion_keywords):
        return False
        
    # Additional Safe Guard:
    # If the text is JUST "cancelled" (very short), we accept it.
    # But if it's "Something Something Cancelled" and not in exclusion, we accept it.
    # But usually "Race Cancelled" is explicit.
    
    return True

def extract_new_post_time(text):
    """
    Extracts new post time from string like "Post Time changed to 1:30 PM".
    Returns formatted time string (HH:MM:SS) or None.
    """
    # Regex for 1:30 PM or 12:45
    # Look for "changed to X:XX PM"
    m = re.search(r'changed to\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)', text, re.IGNORECASE)
    if m:
        time_str = m.group(1).upper()
        # Ensure AM/PM if missing (heuristic?) usually Equibase has it.
        # If input is just 1:30, assuming PM might be risky but standard for afternoon racing.
        # Let's try to convert to HH:MM:00 format if possible, or just return as is if flexible.
        return time_str
    return None

def parse_track_changes(html, track_code):
    """
    Parse the changes table for a specific track.
    Captures Scratches, Jockey Changes, and others.
    """
    changes = []
    if not html: return changes
    
    soup = BeautifulSoup(html, 'html.parser')

    # 1. DATE VALIDATION
    # Look for date in header or body
    # Example: "Late Changes for Thursday, January 22, 2026"
    page_date_valid = False
    
    # Check common date headers
    # <span class="header-date">...</span> or just text search
    try:
        text_content = soup.get_text()
        # Regex for "Changes for [Day], [Month] [Day], [Year]" or "MM/DD/YYYY"
        # Equibase often puts date in a header like <h3>Current Late Changes - Jan 22, 2026</h3>
        
        # We need to match today's date
        today = date.today()
        
        # Strategy: Search for today's formatted string variants
        # 1. "January 22, 2026"
        fmt1 = today.strftime("%B %d, %Y") 
        # 2. "Jan 22, 2026"
        fmt2 = today.strftime("%b %d, %Y")
        # 3. "01/22/2026"
        fmt3 = today.strftime("%m/%d/%Y")
        
        if fmt1 in text_content or fmt2 in text_content or fmt3 in text_content:
            page_date_valid = True
        else:
            # Fallback: Try to parse ANY date and see if it mismatches
            # If we find a date that is NOT today, we reject.
            # If we find NO date, we proceed with caution (or reject? specific pages usually have date).
            # Let's be permissive if no date found (could be fragment), but strict if date FOUND and WRONG.
            
            # Look for explicit date patterns near the top
            header_text = text_content[:1000] # First 1000 chars
            
            # Check for patterns like "Jan 21, 2026" when today is Jan 22
            found_dates = re.findall(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})', header_text)
            for m in found_dates:
                try:
                    d_str = f"{m[0]} {m[1]}, {m[2]}"
                    d_obj = datetime.strptime(d_str, "%b %d, %Y").date()
                    if d_obj != today:
                        logger.warning(f"❌ STALE HTML DETECTED for {track_code}: Found {d_str}, Expected {today}")
                        return [] # Reject entirely
                except: pass
                
    except Exception as e:
        logger.warning(f"Date validation error in HTML: {e}")

    
    # Table usually has id="fullChanges" or similar, but let's be robust
    tables = soup.find_all('table')
    target_table = None
    
    for t in tables:
        if 'Changes' in t.get_text() or t.find('th', class_='changes'):
            target_table = t
            break
            
    if not target_table:
        return changes
        
    current_race = None
    
    rows = target_table.find_all('tr')
    for row in rows:
        # Check for Race Header
        # <tr class="group-header"><th class="race">Race: 1</th>...</tr>
        header_th = row.find('th', class_='race')
        if header_th:
            txt = header_th.get_text(strip=True)
            # "Race: 1"
            m = re.search(r'Race:?\s*(\d+)', txt, re.IGNORECASE)
            if m:
                current_race = int(m.group(1))
            continue
            
        # Check for Change Row
        if not current_race: continue
        
        cols = row.find_all('td')
        
        # Check for Race-wide cancellation row
        # Can be 1 column (colspan) or 2 columns (change + time)
        if len(cols) <= 2:
            # Check all cells for 'cancel'
            is_cancel = False
            txt = ""
            for c in cols:
                c_txt = c.get_text(strip=True)
                if is_valid_cancellation(c_txt):
                    is_cancel = True
                    txt = c_txt
                    break
        
            
            if is_cancel:
                changes.append({
                    'race_number': current_race,
                    'program_number': None,
                    'horse_name': "",
                    'change_type': 'Race Cancelled',
                    'description': txt
                })
                continue

        if len(cols) < 3: continue
        
        # Col 0: Horse (#1 Name)
        # Col 1: Name (sometimes separate?)
        # Let's inspect browser tool result:
        # Row: <td class="horse">#1</td> <td class="horse">Dirty Diana</td> <td class="changes">Scratched - Vet</td>
        
        horse_num_cell = row.find('td', class_='horse')
        if not horse_num_cell: 
            # Check if it's a "Race wide" change but with enough columns?
            change_cell = row.find('td', class_='changes')
            if change_cell:
                txt = change_cell.get_text(strip=True)
                if is_valid_cancellation(txt):
                     changes.append({
                        'race_number': current_race,
                        'program_number': None,
                        'horse_name': "",
                        'change_type': 'Race Cancelled',
                        'description': txt
                    })
            continue
        
        # Sometimes there are two cells with class 'horse' (number, then name)
        horse_cells = row.find_all('td', class_='horse')
        
        pgm = None
        horse_name = None
        change_desc = None
        
        if len(horse_cells) >= 2:
            pgm = horse_cells[0].get_text(strip=True).replace('#', '')
            horse_name = horse_cells[1].get_text(strip=True)
        elif len(horse_cells) == 1:
            # Maybe joined? "#1 Dirty Diana"
            full = horse_cells[0].get_text(strip=True)
            if '#' in full:
                parts = full.split(' ', 1)
                pgm = parts[0].replace('#', '')
                if len(parts) > 1: horse_name = parts[1]
            else:
                horse_name = full
                
        # Change description
        change_cell = row.find('td', class_='changes')
        if change_cell:
            change_desc = normalize_change_description(change_cell.get_text(strip=True))
            
        if change_desc:
            change_type = determine_change_type(change_desc)
            
            changes.append({
                'race_number': current_race,
                'program_number': normalize_pgm(pgm) if pgm else None,
                'horse_name': normalize_name(horse_name if horse_name else ""),
                'change_type': change_type,
                'description': change_desc
            })

    # Also check for whole race cancellation messages in the table or headers if possible
    # Some pages might have a row like "Race 5 Cancelled"
    # We rely on determine_change_type mostly, but let's check header too
    all_headers = target_table.find_all('th', class_='race')
    for h in all_headers:
        txt = h.get_text(strip=True)
        if is_valid_cancellation(txt):
            # Extract race number
            m = re.search(r'Race:?\s*(\d+)', txt, re.IGNORECASE)
            if m:
                r_num = int(m.group(1))
                changes.append({
                    'race_number': r_num,
                    'program_number': None,
                    'horse_name': "",
                    'change_type': 'Race Cancelled',
                    'description': txt
                })
            
    return changes

def fetch_rss_feed(track_code):
    """
    Fetch RSS feed for a track.
    """
    url = f"https://www.equibase.com/static/latechanges/rss/{track_code}-USA.rss"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.text.startswith('<?xml'):
            return r.text
    except Exception as e:
        logger.warning(f"RSS fetch failed for {track_code}: {e}")
    return None

def parse_rss_changes(xml_content, track_code):
    """
    Parse RSS XML to extract changes.
    Validates <pubDate> to ensure relevance.
    """
    soup = BeautifulSoup(xml_content, 'html.parser') # xml parser missing, fallback to html.parser
    items = soup.find_all('item')
    changes = []
    
    today = date.today()
    
    for item in items:
        # DATE VALIDATION
        # <pubDate>Thu, 22 Jan 2026 09:30:00 EST</pubDate>
        pub_date_str = item.pubdate.text if item.pubdate else None
        if not pub_date_str:
            # Fallback: try finding it in description or assume current if RSS cache is trusted?
            # Better to skip if uncertain to avoid the bug.
            # But sometimes pubDate is missing. Check channel?
            pass
        else:
            try:
                # Use email.utils to parse RFC 2822
                dt = parsedate_to_datetime(pub_date_str)
                # Convert to local date (or just compare date part if tz issue)
                # If dt is TZ aware, great.
                if dt.date() != today:
                    logger.debug(f"Skipping stale RSS item dated {dt.date()}")
                    continue
            except Exception as e:
                logger.warning(f"Failed to parse RSS date '{pub_date_str}': {e}")
                # Use caution: if we can't parse date, do we skip? 
                # Given the bug (stale data), we should probably SKIP or check description for date.
                # Let's SKIP to be safe.
                continue

        desc = item.description.text if item.description else ""
        # Description contains multiple lines separated by <br/> (encoded or not)
        # BeautifulSoup XML parser might decode it.
        # Example: "Race 05: <b>...</b> <i>Race Cancelled</i> ..."
        
        # Split by <br/> tags
        lines = re.split(r'<br\s*/?>', desc)
        
        for line in lines:
            if not line.strip(): continue
            
            # 1. Race Cancelled
            # Race 05: <i>Race Cancelled</i> - Weather
            # or &lt;i&gt;Race Cancelled&lt;/i&gt; depending on parsing
            
            # Clean HTML tags from line for easier regex?
            # Or use regex that tolerates tags.
            # "Race (\d+):.*Race Cancelled.*- (.*)"
            
            m_cancel = re.search(r'Race\s*(\d+):.*?Race Cancelled.*?- (.*)', line, re.IGNORECASE | re.DOTALL)
            if m_cancel:
                desc = m_cancel.group(2).strip()
                # Double check with validator just in case regex was too greedy
                if is_valid_cancellation(line) or is_valid_cancellation(desc):
                   changes.append({
                       'race_number': int(m_cancel.group(1)),
                       'program_number': None,
                       'horse_name': "",
                       'change_type': 'Race Cancelled',
                       'description': desc
                   })
                else:
                    # It matched regex but failed validation? 
                    # Maybe "Race 1: Race Cancelled - Show Wagering Cancelled" ??
                    # Log it as Other just in case
                     changes.append({
                       'race_number': int(m_cancel.group(1)),
                       'program_number': None,
                       'horse_name': "",
                       'change_type': 'Wagering' if 'wagering' in desc.lower() else 'Other',
                       'description': desc
                   })
                continue
                
            # 2. Scratch
            # Race 02: <b># 5 A Lister</b> <i>Scratched</i> - Reason Unavailable
            # Regex: Race (\d+):.*?#\s*(\S+)\s+(.*?)</b>.*?Scratched.*?-\s*(.*)
            # Be careful with <b> and </b> items.
            
            # Let's simple remove tags to parse structure
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            # "Race 02: # 5 A Lister Scratched - Reason Unavailable"
            # "Race 02: # 5 A Lister Scratch Reason - Reason Unavailable changed to PrivVet-Injured"
            
            # Parse Race Number
            m_race = re.match(r'Race\s*(\d+):', clean_line)
            if not m_race: continue
            r_num = int(m_race.group(1))
            
            content = clean_line[m_race.end():].strip()
            # "# 5 A Lister Scratched - Reason"
            
            # Parse Horse PGM + Name if present
            # "# 5 A Lister ..."
            pgm = None
            horse_name = None
            
            m_horse = re.match(r'#\s*(\w+)\s+(.*?)\s+(Scratched|Scratch Reason|Jockey|Weight|First Start|Gelding|Correction|Equipment|Workouts)', content, re.IGNORECASE)
            
            if m_horse:
                pgm = m_horse.group(1)
                horse_name = m_horse.group(2)
                keyword = m_horse.group(3) # "Scratched", "Jockey", etc.
                remainder = content[m_horse.end() - len(keyword):] # Start from keyword
            else:
                # Maybe no PGM?
                remainder = content
                
            # Determine Type
            ctype = 'Other'
            if 'scratched' in remainder.lower():
                ctype = 'Scratch'
            elif 'jockey' in remainder.lower():
                ctype = 'Jockey Change'
            elif 'weight' in remainder.lower():
                ctype = 'Weight Change'
            elif 'equipment' in remainder.lower():
                ctype = 'Equipment Change'
                ctype = 'Equipment Change'
            elif is_valid_cancellation(remainder):
                ctype = 'Race Cancelled'
            elif 'post time' in remainder.lower() and 'changed to' in remainder.lower():
                ctype = 'Post Time Change'
            elif 'cancel' in remainder.lower(): # It has cancel but failed valid check -> Wagering/Other
                 if 'wagering' in remainder.lower():
                    ctype = 'Wagering'
                 else:
                    ctype = 'Other'
            
            desc = normalize_change_description(remainder)
            
            changes.append({
                'race_number': r_num,
                'program_number': normalize_pgm(pgm) if pgm else None,
                'horse_name': normalize_name(horse_name if horse_name else ""),
                'change_type': ctype,
                'description': desc
            })
            
    return changes

def process_rss_for_track(track_code):
    """
    Crawl RSS for a specific track and return count of processed.
    """
    logger.info(f"Checking RSS for {track_code}...")
    xml = fetch_rss_feed(track_code)
    if not xml: return 0
    
    changes = parse_rss_changes(xml, track_code)
    logger.info(f"RSS found {len(changes)} changes/cancellations for {track_code}")
    
    today = date.today()
    processed = update_changes_in_db(track_code, today, changes)
    logger.info(f"RSS processed {processed} record(s) for {track_code}")
    return processed

CANCELLATIONS_URL = "https://www.equibase.com/static/latechanges/html/cancellations.html" # Keep for reference or if it starts working


def update_changes_in_db(track_code, race_date, change_list):
    """
    Update database for found changes (scratches and others)
    """
    supabase = get_supabase_client()
    count = 0
    scratches_marked = 0
    
    for item in change_list:
        try:
            # 1. Find Race ID
            race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{item['race_number']}"
            
            # Get Race
            r_res = supabase.table('hranalyzer_races').select('id, race_status').eq('race_key', race_key).execute()
            if not r_res.data:
                continue
                
            race_obj = r_res.data[0]
            race_id = race_obj['id']
            current_status = race_obj.get('race_status', 'open')
            
            # 2. Find Entry to mark
            entry_id = None
            resolved_program_number = item.get('program_number')
            entry_was_scratched = False
            
            # Try PGM match
            if item['program_number']:
                e_res = supabase.table('hranalyzer_race_entries')\
                    .select('id, scratched, program_number')\
                    .eq('race_id', race_id)\
                    .eq('program_number', item['program_number'])\
                    .execute()
                    
                if e_res.data:
                    entry = e_res.data[0]
                    entry_id = entry['id']
                    resolved_program_number = entry.get('program_number') or resolved_program_number
                    entry_was_scratched = bool(entry.get('scratched'))
            
            # Fallback Name match
            if not entry_id and item['horse_name']:
                 all_entries = supabase.table('hranalyzer_race_entries')\
                    .select('id, program_number, scratched, hranalyzer_horses!inner(horse_name)')\
                    .eq('race_id', race_id)\
                    .execute()
                 
                 target_norm = item['horse_name']
                 for e in all_entries.data:
                     h_name = e['hranalyzer_horses']['horse_name']
                     if normalize_name(h_name) == target_norm:
                         entry_id = e['id']
                         resolved_program_number = e.get('program_number') or resolved_program_number
                         entry_was_scratched = bool(e.get('scratched'))
                         break
            
            # ORPHAN PREVENTION:
            # If this is a horse-specific change but we found no horse, DO NOT insert as "Race-wide"
            horse_specific_types = ['Scratch', 'Jockey Change', 'Weight Change', 'Equipment Change']
            if item['change_type'] in horse_specific_types and not entry_id:
                logger.warning(f"⚠️ Skipping orphan {item['change_type']} for {track_code} R{item['race_number']} ({item['horse_name']}/{item['program_number']})")
                continue

            # 3. DEDUPLICATION / MERGE Logic
            # Check if this change already exists (same race, entry, and type)
            query = supabase.table('hranalyzer_changes')\
                .select('id, description')\
                .eq('race_id', race_id)\
                .eq('change_type', item['change_type'])
            
            if entry_id:
                query = query.eq('entry_id', entry_id)
            else:
                query = query.is_('entry_id', 'null')
            
            existing_res = query.execute()
            
            if existing_res.data:
                # SMART DEDUPLICATION
                existing_record = existing_res.data[0]
                existing_desc = existing_record['description'] or ""
                new_desc = normalize_change_description(item['description'])
                
                should_update = False
                final_desc = existing_desc

                # A) Priority Overwrite: If existing is "Unavailable" and new is specific, take new
                if "Reason Unavailable" in existing_desc and "Reason Unavailable" not in new_desc:
                    final_desc = new_desc
                    should_update = True
                
                # B) Ignore: If existing is specific and new is "Unavailable", keep existing
                elif "Reason Unavailable" not in existing_desc and "Reason Unavailable" in new_desc:
                    should_update = False
                    # Do nothing
                    
                # C) Merge: If both are valid, merge if different
                else:
                    normalized_existing = normalize_change_description(existing_desc)
                    if new_desc and new_desc not in normalized_existing:
                         final_desc = normalize_change_description(f"{normalized_existing}; {new_desc}")
                         if len(final_desc) > 500: final_desc = final_desc[:497] + "..."
                         should_update = True
                
                if should_update:
                    supabase.table('hranalyzer_changes')\
                        .update({'description': final_desc})\
                        .eq('id', existing_record['id'])\
                        .execute()
                    count += 1
            else:
                # 4. INSERT into hranalyzer_changes
                change_record = {
                    'race_id': race_id,
                    'entry_id': entry_id,
                    'change_type': item['change_type'],
                    'description': normalize_change_description(item['description'])
                }
                
                try:
                    supabase.table('hranalyzer_changes').insert(change_record).execute()
                    count += 1
                except Exception as e:
                    logger.warning(f"Insert race condition (or duplicate) for {track_code} R{item['race_number']}: {e}")

            # 5. Side effects (Scratched flag, Race Status)
            if item['change_type'] == 'Scratch' and entry_id:
                supabase.table('hranalyzer_race_entries')\
                    .update({'scratched': True})\
                    .eq('id', entry_id)\
                    .execute()

                if entry_was_scratched:
                    logger.info(
                        f"✂️ SCRATCH CONFIRMED: {track_code} R{item['race_number']} "
                        f"#{resolved_program_number} ({item['description']})"
                    )
                else:
                    logger.info(
                        f"✂️ MARKED SCRATCH: {track_code} R{item['race_number']} "
                        f"#{resolved_program_number} ({item['description']})"
                    )
                    scratches_marked += 1
            elif item['change_type'] == 'Race Cancelled':
                # SAFEGUARD: Do not cancel if race is Completed OR has results
                # Check for existing results first
                res_check = supabase.table('hranalyzer_race_entries')\
                    .select('id')\
                    .eq('race_id', race_id)\
                    .in_('finish_position', [1, 2, 3])\
                    .limit(1)\
                    .execute()
                    
                has_results = len(res_check.data) > 0

                if current_status == 'completed' or has_results:
                    logger.warning(f"🛡️ PREVENTED CANCELLATION STATUS for Completed/Resulted Race: {track_code} R{item['race_number']} (Flagged is_cancelled=True)")
                    # Still set the flag for record keeping
                    supabase.table('hranalyzer_races')\
                        .update({
                            'is_cancelled': True, 
                            'cancellation_reason': item['description']
                        })\
                        .eq('id', race_id)\
                        .execute()
                else:
                    # No results? Then it is truly cancelled.
                    # Update status AND flag
                    supabase.table('hranalyzer_races')\
                        .update({
                            'race_status': 'cancelled',
                            'is_cancelled': True,
                            'cancellation_reason': item['description']
                        })\
                        .eq('id', race_id)\
                        .execute()
                    logger.info(f"🚫 RACE CANCELLED: {track_code} R{item['race_number']} ({item['description']})")
                    
            elif item['change_type'] == 'Post Time Change':
                new_time = extract_new_post_time(item['description'])
                if new_time:
                    # Update status to delayed AND update post time
                    updates = {'race_status': 'delayed', 'post_time': new_time}
                    
                    # Convert 1:30 PM to 24hr for postgres TIME column if needed?
                    # Postgres TIME usually handles '01:30 PM' fine.
                    
                    supabase.table('hranalyzer_races')\
                        .update(updates)\
                        .eq('id', race_id)\
                        .execute()
                    logger.info(f"⏰ POST TIME DELAY: {track_code} R{item['race_number']} -> {new_time}")
                else:
                    # Just mark delayed if we can't parse time
                    supabase.table('hranalyzer_races')\
                        .update({'race_status': 'delayed'})\
                        .eq('id', race_id)\
                        .execute()
                    logger.info(f"⚠️ RACE DELAYED (Time Unknown): {track_code} R{item['race_number']}")
            
        except Exception as e:
            logger.error(f"Error processing change {item}: {e}")
            
    return count

def crawl_otb_changes(fetch_telemetry=None):
    """
    Fallback crawler for OffTrackBetting.com
    Returns number of changes processed.
    """
    # ... (Keep existing OTB logic as is for now, heavily truncated for brevity in replacement if needed, 
    # but since I'm replacing from line 273, I need to keep it or just reference it?)
    # Wait, I shouldn't truncate OTB logic if I'm replacing the whole file bottom or a large chunk.
    # The user asked to modify crawl_scratches.py.
    # I will assume I need to keep OTB logic intact.
    
    # RE-IMPLEMENTING OTB fetch to ensure file integrity since I am replacing a huge chunk
    logger.info("Starting Fallback Crawl: OTB Scratches & Changes")
    url = "https://www.offtrackbetting.com/scratches_changes.html"
    
    html = fetch_static_page(url, telemetry=fetch_telemetry)
    if not html:
        logger.error("Failed to fetch OTB page")
        return 0
        
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    main_table = None
    for t in tables:
        if 'Race Date:' in t.get_text():
            main_table = t
            break
            
    today = date.today() # Target date
    
    # 1. Validate Date
    if 'Race Date:' not in main_table.get_text():
        logger.warning("OTB: Could not find Race Date header.")
        return 0
        
    # Extract date text "Race Date: 01/18/2026"
    date_valid = False
    try:
        import re
        txt = main_table.get_text()
        m = re.search(r'Race Date:\s*(\d{1,2}/\d{1,2}/\d{4})', txt)
        if m:
            page_date_str = m.group(1)
            # Parse MM/DD/YYYY
            page_date = datetime.strptime(page_date_str, '%m/%d/%Y').date()
            if page_date == today:
                date_valid = True
            else:
                logger.warning(f"OTB: Stale date found. Page: {page_date}, Expected: {today}. SKIPPING OTB.")
                return 0
    except Exception as e:
        logger.warning(f"OTB: Date validation error: {e}")
        return 0
        
    if not date_valid:
        return 0

    rows = main_table.find_all('tr')
    
    current_track = None
    current_race = None
    changes_found = []
    
    last_pgm = None
    last_horse = None
    
    for row in rows:
        text = row.get_text(strip=True)
        if 'Change' in text and ':' in text:
             last_pgm = None
             last_horse = None
             cols = row.find_all('td')
             if cols:
                 header_txt = cols[0].get_text(strip=True)
                 parts = header_txt.split(':')
                 if len(parts) >= 3:
                     current_track = parts[0].strip()
                     race_part = parts[-1].lower().replace('race', '').strip()
                     current_race = int(race_part) if race_part.isdigit() else None
             continue
             
        if not current_track or not current_race: continue
            
        cols = row.find_all('td')
        if len(cols) < 3: continue
        
        pgm = None
        horse_name = None
        desc_cell = None
        
        if len(cols) == 4 and '#' in cols[0].get_text():
            pgm = cols[0].get_text(strip=True).replace('#', '')
            horse_name = cols[1].get_text(strip=True)
            desc_cell = cols[2]
            last_pgm = pgm
            last_horse = horse_name
            
        elif len(cols) == 3 and not '#' in cols[0].get_text():
             # Strict check: preventing spillover if this row lacks structure
             # Only assume spillover if last_horse is set AND this row looks like a continuation
             # But OTB format for "Reason" alone usually implies it belongs to above.
             desc_cell = cols[1]
             pgm = last_pgm
             horse_name = last_horse
        
        if desc_cell:
            raw_desc = desc_cell.get_text(" ", strip=True).replace('\n', ' ').strip()
            ctype = determine_change_type(raw_desc)
            changes_found.append({
                'track_code': current_track,
                'race_number': current_race,
                'program_number': pgm, 
                'horse_name': horse_name,
                'change_type': ctype,
                'description': raw_desc
            })
    
    changes_by_track = {}
    for c in changes_found:
        t = c['track_code']
        if t not in changes_by_track: changes_by_track[t] = []
        changes_by_track[t].append(c)
        
    total_saved = 0
    today = date.today()
    for trk, chgs in changes_by_track.items():
        total_saved += update_changes_in_db(trk, today, chgs)
        
    logger.info(
        "OTB processed %s record(s) using %s",
        total_saved,
        _format_fetcher_label(fetch_telemetry),
    )
    return total_saved


def crawl_late_changes(reset_first=False, preferred_tracks=None):
    """
    Main entry point for crawling changes.
    """
    logger.info(f"Starting Crawl: Equibase Late Changes (Reset={reset_first})")
    
    total_changes_processed = 0
    today = date.today()
    source_counts = {
        'rss': 0,
        'direct_html': 0,
        'mobile_html': 0,
        'index_html': 0,
        'otb': 0,
    }
    fetch_telemetry = {}
    
    # Reset Logic
    if reset_first:
        # We need a list of active tracks to reset.
        # We'll use the same active track discovery logic.
        pass # Will be handled inside the discovery loop or separate query?
        # Actually better to do it per track as we find them valid?
        # No, reset implies "I want a clean slate". 
        # But we only know *active* tracks for today from DB races.
        # So we query active tracks first.

    
    # 0. CHECK RSS FEEDS (Primary method now due to Equibase blocking)
    logger.info("Checking RSS feeds for active tracks...")
    
    # Get active tracks from DB for today
    today_str = today.strftime('%Y%m%d')
    supabase = get_supabase_client()
    try:
        # Get unique track codes for races today
        res = supabase.table('hranalyzer_races')\
            .select('race_key')\
            .like('race_key', f"%-{today_str}-%")\
            .execute()
        
        active_tracks = set()
        if res.data:
            for r in res.data:
                # key: AQU-20260117-1
                parts = r['race_key'].split('-')
                if len(parts) >= 1:
                    active_tracks.add(parts[0])
        
        if preferred_tracks:
            preferred_tracks = {code.upper() for code in preferred_tracks}
            active_tracks = {code for code in active_tracks if code in preferred_tracks}

        logger.info(f"Active tracks to scan: {list(active_tracks)}")
        
        # EXECUTE RESET if requested
        if reset_first:
            for trk in active_tracks:
                reset_scratches_for_date(trk, today)
        
        for trk in active_tracks:
            cnt = process_rss_for_track(trk)
            total_changes_processed += cnt
            source_counts['rss'] += cnt
            
    except Exception as e:
        logger.error(f"RSS Scan Loop failed: {e}")

    # 0.5. Direct per-track HTML fetch on TVG/legacy static hosts
    # This is more reliable than the legacy index page and covers tracks like GP
    # even when the index is blocked or incomplete.
    try:
        for trk in active_tracks:
            direct_fetch_meta = {}
            html, source_url = fetch_direct_track_changes_page(trk, telemetry=direct_fetch_meta)
            _merge_fetch_telemetry(fetch_telemetry, direct_fetch_meta)
            source_name = 'direct_html'
            if not html:
                changes = []
            else:
                changes = parse_track_changes(html, trk)
            if not changes:
                mobile_fetch_meta = {}
                mobile_html, mobile_url = fetch_mobile_track_changes_page(trk, telemetry=mobile_fetch_meta)
                _merge_fetch_telemetry(fetch_telemetry, mobile_fetch_meta)
                if mobile_html:
                    changes = parse_mobile_track_changes(mobile_html, trk)
                    source_url = mobile_url
                    fetcher_label = _format_fetcher_label(mobile_fetch_meta)
                    source_name = 'mobile_html'
                else:
                    fetcher_label = _format_fetcher_label(direct_fetch_meta)
            else:
                fetcher_label = _format_fetcher_label(direct_fetch_meta)
            if changes:
                count = update_changes_in_db(trk, today, changes)
                total_changes_processed += count
                source_counts[source_name] += count
                logger.info(
                    "Direct late-changes HTML processed %s record(s) for %s via %s using %s",
                    count,
                    trk,
                    source_url,
                    fetcher_label,
                )
    except Exception as e:
        logger.error(f"Direct track late-changes fetch failed: {e}")

    # 1. Try Equibase Track Pages (HTML Fallback)
    try:
        index_fetch_meta = {}
        track_links = parse_late_changes_index(telemetry=index_fetch_meta) # This might be blocked too
        _merge_fetch_telemetry(fetch_telemetry, index_fetch_meta)
        if track_links:
            logger.info(
                "Found %s tracks with changes on Equibase HTML index using %s",
                len(track_links),
                _format_fetcher_label(index_fetch_meta),
            )
            for link in track_links:
                code = link['track_code']
                if preferred_tracks and code.upper() not in preferred_tracks:
                    continue
                # Skip if we already did RSS for this track? 
                # Maybe good to double check but duplicates are handled.
                # If RSS fails, this might work (via PowerShell)
                url = link['url']
                try:
                    page_fetch_meta = {}
                    html = fetch_static_page(url, telemetry=page_fetch_meta)
                    _merge_fetch_telemetry(fetch_telemetry, page_fetch_meta)
                    if html:
                        changes = parse_track_changes(html, code)
                        if changes:
                            count = update_changes_in_db(code, today, changes)
                            total_changes_processed += count
                            source_counts['index_html'] += count
                            logger.info(
                                "Equibase index HTML processed %s record(s) for %s via %s using %s",
                                count,
                                code,
                                url,
                                _format_fetcher_label(page_fetch_meta),
                            )
                except Exception as e:
                    logger.error(f"Error crawling {code}: {e}")
    except Exception as e:
        logger.error(f"Equibase index fetch failed: {e}")
        
    logger.info(f"Equibase phase complete. Total records: {total_changes_processed}")
    
    # 2. Run OTB Fallback
    logger.info("Starting OTB Fallback Crawl...")
    try:
        otb_fetch_meta = {}
        otb_count = crawl_otb_changes(fetch_telemetry=otb_fetch_meta)
        _merge_fetch_telemetry(fetch_telemetry, otb_fetch_meta)
        total_changes_processed += otb_count
        source_counts['otb'] += otb_count
        logger.info(f"OTB Helper added records.")
    except Exception as e:
        logger.error(f"OTB Crawl failed: {e}")

    logger.info("Late-change contribution summary: %s", _summarize_contributions(source_counts))
    logger.info("HTML fetch success summary: %s", _summarize_fetchers(fetch_telemetry))
        
    return total_changes_processed

def reset_scratches_for_date(track_code, race_date):
    """
    Hard reset scratches for a track/date. 
    Used when we suspect 'ghost scratches' from bad crawl data.
    """
    logger.info(f"RESETTING SCRATCHES for {track_code} on {race_date}")
    supabase = get_supabase_client()
    
    try:
        race_date_str = race_date.strftime('%Y-%m-%d')
        
        # 1. Get relevant race IDs
        races = supabase.table('hranalyzer_races')\
            .select('id')\
            .eq('track_code', track_code)\
            .eq('race_date', race_date_str)\
            .execute()
            
        race_ids = [r['id'] for r in races.data]
        if not race_ids:
            logger.warning("No races found to reset.")
            return
            
        # 2. Un-scratch ALL entries in these races
        supabase.table('hranalyzer_race_entries')\
            .update({'scratched': False})\
            .in_('race_id', race_ids)\
            .execute()
            
        # 3. Delete ALL detailed changes from hranalyzer_changes for these races
        # This ensures we remove stale "Jockey Changes", "Owner Changes", etc. that are no longer valid.
        supabase.table('hranalyzer_changes')\
            .delete()\
            .in_('race_id', race_ids)\
            .execute()
            
        logger.info(f"Successfully reset scratches for {len(race_ids)} races.")
        
    except Exception as e:
        logger.error(f"Failed to reset scratches: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    crawl_late_changes()
