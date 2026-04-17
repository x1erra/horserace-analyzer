"""
Equibase Crawler for Historical Race Data
Crawls Equibase race chart PDFs and inserts results into Supabase database
Uses local Python parsing - NO API COSTS!
"""

import os
import sys
import logging
import time
import re
import gc
import atexit
import shutil
import base64
import tempfile
import requests
import subprocess
from collections import defaultdict
import cloudscraper
import pdfplumber
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from supabase_client import get_supabase_client
from dotenv import load_dotenv
from runtime_state import record_scratch_event

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - dependency is installed in production images
    curl_requests = None

try:
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except ImportError:  # pragma: no cover - dependency is installed in scheduler image
    webdriver = None
    WebDriverException = Exception
    Options = None
    Service = None

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Common US tracks (expand as needed)
COMMON_TRACKS = [
    'AQU', 'BEL', 'CD', 'DMR', 'FG', 'GP', 'HOU', 'KEE', 'SA', 'SAR',
    'TAM', 'WO', 'MD', 'PRX', 'PIM', 'MVR', 'TUP', 'WRD'
]

DEFAULT_BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.equibase.com/',
}
COOKIE_CACHE_TTL_SECONDS = 20 * 60
_equibase_cookie_cache = {'cookies': None, 'fetched_at': 0.0}
CHROMIUM_MIN_HEADROOM_BYTES = int(os.getenv('EQUIBASE_CHROMIUM_MIN_HEADROOM_MB', '512')) * 1024 * 1024
POWERSHELL_MIN_HEADROOM_BYTES = int(os.getenv('EQUIBASE_PWSH_MIN_HEADROOM_MB', '192')) * 1024 * 1024
SHARED_BROWSER_MAX_AGE_SECONDS = int(os.getenv('EQUIBASE_BROWSER_MAX_AGE_SECONDS', '900'))
SHARED_BROWSER_MAX_DOWNLOADS = int(os.getenv('EQUIBASE_BROWSER_MAX_DOWNLOADS', '18'))
HEAVY_FALLBACK_FAILURE_THRESHOLD = int(os.getenv('EQUIBASE_HEAVY_FAILURE_THRESHOLD', '3'))
HEAVY_FALLBACK_COOLDOWN_SECONDS = int(os.getenv('EQUIBASE_HEAVY_COOLDOWN_SECONDS', '900'))
_equibase_browser_session = {
    'driver': None,
    'download_dir': None,
    'tempdir': None,
    'created_at': 0.0,
    'uses': 0,
}
_heavy_fallback_state = {
    'powershell': {'failures': 0, 'cooldown_until': 0.0},
    'selenium': {'failures': 0, 'cooldown_until': 0.0},
}


def _read_cgroup_int(*paths: str) -> Optional[int]:
    """Read the first available cgroup memory value."""
    for path in paths:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                raw = fh.read().strip()
        except OSError:
            continue

        if not raw or raw == 'max':
            return None

        try:
            value = int(raw)
        except ValueError:
            continue

        # cgroup v1 may expose a very large sentinel when no limit is set.
        if value <= 0 or value >= (1 << 60):
            return None
        return value

    return None


def get_container_memory_usage_bytes() -> Optional[int]:
    return _read_cgroup_int(
        '/sys/fs/cgroup/memory.current',
        '/sys/fs/cgroup/memory/memory.usage_in_bytes',
    )


def get_container_memory_limit_bytes() -> Optional[int]:
    return _read_cgroup_int(
        '/sys/fs/cgroup/memory.max',
        '/sys/fs/cgroup/memory/memory.limit_in_bytes',
    )


def has_container_memory_headroom(minimum_bytes: int, label: str) -> bool:
    """
    Guard heavy fallbacks against the scheduler's cgroup limit, not host RAM.
    """
    usage = get_container_memory_usage_bytes()
    limit = get_container_memory_limit_bytes()
    if usage is None or limit is None:
        return True

    remaining = limit - usage
    if remaining >= minimum_bytes:
        return True

    logger.warning(
        "Skipping %s: only %.1f MB headroom remains under container limit (usage=%.1f MB, limit=%.1f MB)",
        label,
        remaining / (1024 * 1024),
        usage / (1024 * 1024),
        limit / (1024 * 1024),
    )
    return False


def format_container_memory_summary() -> str:
    usage = get_container_memory_usage_bytes()
    limit = get_container_memory_limit_bytes()
    if usage is None or limit is None:
        return "container_memory=unknown"

    remaining = max(0, limit - usage)
    return (
        f"container_memory usage={usage / (1024 * 1024):.1f}MB "
        f"limit={limit / (1024 * 1024):.1f}MB "
        f"headroom={remaining / (1024 * 1024):.1f}MB"
    )


def log_container_memory(label: str) -> None:
    logger.info("%s | %s", label, format_container_memory_summary())


def heavy_fallback_available(name: str) -> bool:
    state = _heavy_fallback_state[name]
    cooldown_until = state.get('cooldown_until', 0.0)
    if cooldown_until <= time.time():
        return True

    remaining = max(0, int(cooldown_until - time.time()))
    logger.warning(
        "Skipping %s fallback: circuit breaker open for %ss after repeated failures",
        name,
        remaining,
    )
    return False


def record_heavy_fallback_success(name: str) -> None:
    state = _heavy_fallback_state[name]
    if state.get('failures', 0) or state.get('cooldown_until', 0.0):
        logger.info("Reset %s fallback circuit after a successful attempt", name)
    state['failures'] = 0
    state['cooldown_until'] = 0.0


def record_heavy_fallback_failure(name: str) -> None:
    state = _heavy_fallback_state[name]
    state['failures'] = state.get('failures', 0) + 1
    if state['failures'] < HEAVY_FALLBACK_FAILURE_THRESHOLD:
        return

    state['cooldown_until'] = time.time() + HEAVY_FALLBACK_COOLDOWN_SECONDS
    logger.warning(
        "Opening %s fallback circuit for %ss after %s consecutive failures",
        name,
        HEAVY_FALLBACK_COOLDOWN_SECONDS,
        state['failures'],
    )
    state['failures'] = 0


def close_shared_equibase_webdriver(reason: str = "") -> None:
    """Tear down the shared Chromium session and its download directory."""
    driver = _equibase_browser_session.get('driver')
    tempdir = _equibase_browser_session.get('tempdir')

    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass

    if tempdir is not None:
        try:
            tempdir.cleanup()
        except Exception:
            pass

    _equibase_browser_session.update(
        {
            'driver': None,
            'download_dir': None,
            'tempdir': None,
            'created_at': 0.0,
            'uses': 0,
        }
    )

    if reason:
        logger.info("Closed shared Equibase browser session (%s)", reason)


def clear_shared_browser_download_dir() -> None:
    """Prevent stale files from being misread as the current download."""
    download_dir = _equibase_browser_session.get('download_dir')
    if not download_dir or not os.path.isdir(download_dir):
        return

    for name in os.listdir(download_dir):
        path = os.path.join(download_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            os.remove(path)
        except OSError:
            continue


def get_shared_equibase_webdriver(timeout: int = 45):
    """
    Reuse one Chromium instance across PDF downloads instead of launching one per race.
    """
    driver = _equibase_browser_session.get('driver')
    should_rotate = False

    if driver is not None:
        age_seconds = time.time() - (_equibase_browser_session.get('created_at') or 0.0)
        if age_seconds > SHARED_BROWSER_MAX_AGE_SECONDS:
            should_rotate = True
        elif _equibase_browser_session.get('uses', 0) >= SHARED_BROWSER_MAX_DOWNLOADS:
            should_rotate = True
        else:
            try:
                driver.current_url
            except Exception:
                should_rotate = True

    if should_rotate:
        close_shared_equibase_webdriver(reason="rotation")
        driver = None

    if driver is None:
        if not has_container_memory_headroom(CHROMIUM_MIN_HEADROOM_BYTES, "Chromium Equibase fallback"):
            return None

        tempdir = tempfile.TemporaryDirectory(prefix='equibase_browser_')
        driver = create_equibase_webdriver(download_dir=tempdir.name, timeout=timeout)
        if driver is None:
            tempdir.cleanup()
            return None

        _equibase_browser_session.update(
            {
                'driver': driver,
                'download_dir': tempdir.name,
                'tempdir': tempdir,
                'created_at': time.time(),
                'uses': 0,
            }
        )
        logger.info("Created shared Chromium session for Equibase PDF retrieval")

    _equibase_browser_session['uses'] = _equibase_browser_session.get('uses', 0) + 1
    clear_shared_browser_download_dir()
    return _equibase_browser_session['driver']


atexit.register(close_shared_equibase_webdriver)


def normalize_name(name: str) -> str:
    """
    Normalize name for more reliable mapping (strip non-alphanumeric, lowercase)
    Also removes country codes/suffixes like (IRE), (GB), etc.
    """
    if not name:
        return ""
    
    # Remove parens and content inside them (e.g. "Horse Name (IRE)" -> "Horse Name")
    name = re.sub(r'\s*\(.*?\)', '', name)
    
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()


def normalize_pgm(pgm: str) -> str:
    """
    Normalize program number (e.g. '08' -> '8', '1A' -> '1A')
    """
    if not pgm:
        return "0"
    
    pgm = str(pgm).strip().upper()
    
    # STRICTER CLEANING: Remove anything that is not alphanumeric
    # This handles "1*", "3 (Part)", etc.
    pgm = re.sub(r'[^A-Z0-9]', '', pgm)
    
    # Remove leading zeros if it's numeric-ish (but keep '0' if it is just '0')
    # Actually just stripping leading zeros works for '01', '01A' -> '1A'
    
    # If strictly numeric, simple int conversion
    if pgm.isdigit():
        return str(int(pgm))
        
    # If alphanumeric, try to strip leading zeros from the numeric part? 
    # E.g. "01A" -> "1A". 
    pgm = re.sub(r'^0+', '', pgm)
    
    return pgm if pgm else "0"



def build_equibase_url(track_code: str, race_date: date, race_number: int) -> str:
    """
    Build the accessible TVG-hosted Equibase PDF URL for a specific race.
    Format: https://tvg.equibase.com/static/chart/pdf/TTMMDDYYUSAN.pdf

    Example: GP on 01/04/2024, Race 1 -> https://tvg.equibase.com/static/chart/pdf/GP010424USA1.pdf
    """
    mm = race_date.strftime('%m')
    dd = race_date.strftime('%d')
    yy = race_date.strftime('%y')

    url = f"https://tvg.equibase.com/static/chart/pdf/{track_code}{mm}{dd}{yy}USA{race_number}.pdf"
    return url


def build_equibase_full_card_url(track_code: str, race_date: date) -> str:
    """Build the accessible TVG-hosted full-card Equibase PDF URL for a track/date."""
    mm = race_date.strftime('%m')
    dd = race_date.strftime('%d')
    yy = race_date.strftime('%y')
    return f"https://tvg.equibase.com/static/chart/pdf/{track_code}{mm}{dd}{yy}USA.pdf"


def parse_equibase_static_pdf_url(pdf_url: str) -> Optional[Tuple[str, date, int]]:
    """Extract track/date/race_number from a static chart PDF URL."""
    match = re.search(r'/([A-Z]{2,4})(\d{2})(\d{2})(\d{2})USA(\d+)\.pdf(?:\?.*)?$', pdf_url)
    if not match:
        return None

    track_code, mm, dd, yy, race_number = match.groups()
    race_date = datetime.strptime(f'{mm}{dd}{yy}', '%m%d%y').date()
    return track_code, race_date, int(race_number)


def is_pdf_bytes(content: Optional[bytes]) -> bool:
    """Cheap validation that a response is actually a PDF."""
    return bool(content and content.startswith(b'%PDF'))


def build_race_map(races: List[Dict]) -> Dict[int, Dict]:
    """Index parsed races by race number for quick reuse."""
    race_map = {}
    for race in races or []:
        try:
            race_number = int(race.get('race_number') or 0)
        except (TypeError, ValueError):
            continue
        if race_number and race.get('horses'):
            race_map[race_number] = race
    return race_map


def page_looks_like_imperva(html: Optional[str]) -> bool:
    """Detect the Imperva interstitial Equibase is serving to the crawler."""
    normalized = (html or '').lower()
    return (
        'pardon our interruption' in normalized
        or 'onprotectioninitialized' in normalized
        or 'imperva' in normalized
    )


def create_equibase_webdriver(download_dir: Optional[str] = None, timeout: int = 45):
    """Create a Chromium webdriver configured for Equibase and optional file downloads."""
    if webdriver is None or Options is None:
        logger.warning("selenium is not installed; cannot launch Chromium for Equibase")
        return None

    options = Options()
    for arg in (
        '--headless=new',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--window-size=1400,1200',
    ):
        options.add_argument(arg)

    prefs = {
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'plugins.always_open_pdf_externally': True,
        'safebrowsing.enabled': True,
    }
    if download_dir:
        prefs['download.default_directory'] = download_dir
    options.add_experimental_option('prefs', prefs)

    for binary in ('/usr/bin/chromium', '/usr/bin/chromium-browser'):
        if os.path.exists(binary):
            options.binary_location = binary
            break

    service_path = shutil.which('chromedriver')
    service = Service(executable_path=service_path) if service_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(timeout)

    if download_dir:
        for command in ('Page.setDownloadBehavior', 'Browser.setDownloadBehavior'):
            try:
                driver.execute_cdp_cmd(
                    command,
                    {
                        'behavior': 'allow',
                        'downloadPath': download_dir,
                        'eventsEnabled': True,
                    },
                )
                break
            except Exception:
                continue

    return driver


def warm_equibase_browser_session(driver, target_url: str, timeout: int) -> bool:
    """Load an Equibase page and wait for the Imperva interstitial to clear."""
    try:
        driver.get(target_url)
    except Exception as e:
        logger.warning(f"Chromium warm-up navigation failed for {target_url}: {e}")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            html = driver.page_source
        except Exception:
            html = ''
        if not page_looks_like_imperva(html):
            return True
        time.sleep(1)

    logger.warning("Chromium session remained on the Imperva interstitial for %s", target_url)
    return False


def fetch_pdf_via_browser_context(driver, pdf_url: str, timeout: int = 30) -> Optional[bytes]:
    """Fetch the PDF inside the live browser session after Equibase challenge clearance."""
    script = """
const url = arguments[0];
const done = arguments[arguments.length - 1];
fetch(url, {
  credentials: 'include',
  headers: { 'Accept': 'application/pdf,application/octet-stream,*/*' }
}).then(async (response) => {
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  done({
    status: response.status,
    contentType: response.headers.get('content-type') || '',
    body: btoa(binary),
  });
}).catch((error) => done({ error: String(error) }));
"""

    try:
        driver.set_script_timeout(timeout)
        result = driver.execute_async_script(script, pdf_url)
        if not isinstance(result, dict):
            logger.warning("selenium browser fetch returned an unexpected payload for %s", pdf_url)
            return None
        if result.get('error'):
            logger.warning("selenium browser fetch error for %s: %s", pdf_url, result['error'])
            return None

        content = base64.b64decode(result.get('body') or '')
        if result.get('status') == 200 and is_pdf_bytes(content):
            logger.info(f"selenium browser fetch downloaded PDF ({len(content)} bytes)")
            return content
        logger.warning(
            "selenium browser fetch failed with status %s and content type %s",
            result.get('status'),
            result.get('contentType'),
        )
    except Exception as e:
        logger.warning(f"selenium browser fetch error for {pdf_url}: {e}")

    return None


def wait_for_downloaded_pdf(download_dir: str, timeout: int = 30) -> Optional[bytes]:
    """Wait for Chromium to place a PDF into the download directory."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            entries = os.listdir(download_dir)
        except FileNotFoundError:
            return None

        for name in entries:
            if name.endswith(('.crdownload', '.tmp', '.part')):
                continue
            path = os.path.join(download_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, 'rb') as fh:
                    content = fh.read()
            except OSError:
                continue
            if is_pdf_bytes(content):
                return content

        time.sleep(1)

    return None


def download_pdf_via_cookie_replay(
    pdf_url: str,
    cookies: Optional[Dict[str, str]],
    timeout: int = 60,
) -> Optional[bytes]:
    """Replay a PDF request via requests using browser-acquired cookies."""
    if not cookies:
        return None

    try:
        response = requests.get(
            pdf_url,
            headers=DEFAULT_BROWSER_HEADERS,
            cookies=cookies,
            timeout=timeout,
        )
        if response.status_code == 200 and is_pdf_bytes(response.content):
            logger.info(f"selenium cookie replay downloaded PDF ({len(response.content)} bytes)")
            return response.content
        logger.warning(
            "selenium cookie replay failed with status %s and content type %s",
            response.status_code,
            response.headers.get('Content-Type'),
        )
    except Exception as e:
        logger.warning(f"selenium cookie replay error for {pdf_url}: {e}")

    return None


def download_pdf_via_curl_cffi(pdf_url: str, timeout: int = 40) -> Optional[bytes]:
    if curl_requests is None:
        return None

    try:
        response = curl_requests.get(
            pdf_url,
            headers=DEFAULT_BROWSER_HEADERS,
            impersonate='chrome',
            timeout=timeout,
        )
        if response.status_code == 200 and is_pdf_bytes(response.content):
            logger.info(f"curl_cffi downloaded PDF ({len(response.content)} bytes)")
            return response.content
        if response.status_code == 404:
            logger.warning(f"curl_cffi got 404 for {pdf_url}")
            return None
        logger.warning(
            "curl_cffi static download failed with status %s and content type %s",
            response.status_code,
            response.headers.get('Content-Type'),
        )
    except Exception as e:
        logger.warning(f"curl_cffi static download error for {pdf_url}: {e}")

    return None


def download_pdf_via_cloudscraper(pdf_url: str, timeout: int = 40) -> Optional[bytes]:
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(pdf_url, headers=DEFAULT_BROWSER_HEADERS, timeout=timeout)
        if response.status_code == 200 and is_pdf_bytes(response.content):
            logger.info(f"cloudscraper downloaded PDF ({len(response.content)} bytes)")
            return response.content
        if response.status_code == 404:
            logger.warning(f"cloudscraper got 404 for {pdf_url}")
            return None
        logger.warning(
            "cloudscraper static download failed with status %s and content type %s",
            response.status_code,
            response.headers.get('Content-Type'),
        )
    except Exception as e:
        logger.warning(f"cloudscraper static download error for {pdf_url}: {e}")

    return None


def download_pdf_via_requests(pdf_url: str, timeout: int = 40) -> Optional[bytes]:
    try:
        response = requests.get(pdf_url, headers=DEFAULT_BROWSER_HEADERS, timeout=timeout)
        if response.status_code == 200 and is_pdf_bytes(response.content):
            logger.info(f"requests downloaded PDF ({len(response.content)} bytes)")
            return response.content
        if response.status_code == 404:
            logger.warning(f"requests got 404 for {pdf_url}")
            return None
        logger.warning(
            "requests static download failed with status %s and content type %s",
            response.status_code,
            response.headers.get('Content-Type'),
        )
    except Exception as e:
        logger.warning(f"requests static download error for {pdf_url}: {e}")

    return None


def get_equibase_browser_cookies(target_url: str, timeout: int = 45) -> Optional[Dict[str, str]]:
    """Use headless Chromium to satisfy Imperva and capture a valid Equibase cookie jar."""
    cached = _equibase_cookie_cache.get('cookies')
    fetched_at = _equibase_cookie_cache.get('fetched_at', 0.0)
    if cached and (time.time() - fetched_at) < COOKIE_CACHE_TTL_SECONDS:
        return cached

    try:
        logger.info("Launching headless Chromium to satisfy Equibase protection")
        driver = get_shared_equibase_webdriver(timeout=timeout)
        if driver is None:
            return None
        warm_equibase_browser_session(driver, target_url, timeout)

        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        if cookies:
            _equibase_cookie_cache['cookies'] = cookies
            _equibase_cookie_cache['fetched_at'] = time.time()
            logger.info(f"Captured {len(cookies)} Equibase browser cookies")
            return cookies
        logger.warning("Browser session completed without any Equibase cookies")
    except WebDriverException as e:
        logger.warning(f"Chromium fallback failed while solving Equibase challenge: {e}")
        close_shared_equibase_webdriver(reason="webdriver error while fetching cookies")
    except Exception as e:
        logger.warning(f"Unexpected Chromium fallback error: {e}")
        close_shared_equibase_webdriver(reason="unexpected error while fetching cookies")

    return None


def download_pdf_via_selenium(pdf_url: str, timeout: int = 60) -> Optional[bytes]:
    """Last-resort downloader that uses a real browser session before falling back to cookie replay."""
    if not heavy_fallback_available('selenium'):
        return None

    cookies = None

    try:
        logger.info("Reusing shared Chromium session for Equibase PDF retrieval")
        driver = get_shared_equibase_webdriver(timeout=min(timeout, 45))
        if driver is None:
            return None

        warm_equibase_browser_session(driver, 'https://www.equibase.com/', min(timeout, 25))

        content = fetch_pdf_via_browser_context(driver, pdf_url, timeout=min(timeout, 25))
        if content:
            record_heavy_fallback_success('selenium')
            return content

        try:
            driver.get(pdf_url)
        except Exception as e:
            logger.warning(f"selenium browser navigation error for {pdf_url}: {e}")

        download_dir = _equibase_browser_session.get('download_dir')
        content = wait_for_downloaded_pdf(download_dir, timeout=min(timeout, 25)) if download_dir else None
        if content:
            logger.info(f"selenium browser download captured PDF ({len(content)} bytes)")
            record_heavy_fallback_success('selenium')
            return content

        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        if cookies:
            _equibase_cookie_cache['cookies'] = cookies
            _equibase_cookie_cache['fetched_at'] = time.time()
    except WebDriverException as e:
        logger.warning(f"Chromium PDF retrieval failed for {pdf_url}: {e}")
        record_heavy_fallback_failure('selenium')
        close_shared_equibase_webdriver(reason="webdriver error during PDF retrieval")
    except Exception as e:
        logger.warning(f"Unexpected Chromium PDF retrieval error for {pdf_url}: {e}")
        record_heavy_fallback_failure('selenium')
        close_shared_equibase_webdriver(reason="unexpected error during PDF retrieval")

    replayed = download_pdf_via_cookie_replay(pdf_url, cookies, timeout=timeout)
    if replayed:
        record_heavy_fallback_success('selenium')
        return replayed

    record_heavy_fallback_failure('selenium')
    return None


def download_pdf_via_powershell(pdf_url: str, timeout: int = 45) -> Optional[bytes]:
    """Last-resort downloader using pwsh inside the production container image."""
    if shutil.which("pwsh") is None:
        return None
    if not heavy_fallback_available('powershell'):
        return None
    if not has_container_memory_headroom(POWERSHELL_MIN_HEADROOM_BYTES, "PowerShell Equibase fallback"):
        return None

    temp_file = f"/tmp/equibase_{int(time.time())}_{os.getpid()}.pdf"
    script = (
        "$ProgressPreference='SilentlyContinue'; "
        "$headers=@{"
        f"'User-Agent'='{DEFAULT_BROWSER_HEADERS['User-Agent']}';"
        f"'Accept'='{DEFAULT_BROWSER_HEADERS['Accept']}';"
        f"'Referer'='{DEFAULT_BROWSER_HEADERS['Referer']}'"
        "}; "
        f"Invoke-WebRequest -Uri '{pdf_url}' -Headers $headers -OutFile '{temp_file}' -TimeoutSec {timeout}"
    )

    try:
        result = subprocess.run(
            ["pwsh", "-NoLogo", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(f"pwsh download failed for {pdf_url}: {result.stderr.strip()}")
            record_heavy_fallback_failure('powershell')
            return None
        if not os.path.exists(temp_file):
            logger.warning(f"pwsh did not produce a file for {pdf_url}")
            record_heavy_fallback_failure('powershell')
            return None
        with open(temp_file, 'rb') as fh:
            content = fh.read()
        if is_pdf_bytes(content):
            logger.info(f"pwsh downloaded PDF ({len(content)} bytes)")
            record_heavy_fallback_success('powershell')
            return content
        logger.warning(f"pwsh download for {pdf_url} was not a PDF")
        record_heavy_fallback_failure('powershell')
    except Exception as e:
        logger.warning(f"pwsh static download error for {pdf_url}: {e}")
        record_heavy_fallback_failure('powershell')
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

    return None


def download_full_card_pdf(track_code: str, race_date: date, timeout: int = 60) -> Optional[bytes]:
    """
    Download the premium full-card Equibase PDF using a browser-impersonated client.
    This is more reliable than the static chart endpoint when Equibase's WAF is aggressive.
    """
    url = build_equibase_full_card_url(track_code, race_date)
    if curl_requests is not None:
        try:
            logger.info(f"Attempting full-card PDF for {track_code} {race_date} via curl_cffi")
            response = curl_requests.get(
                url,
                headers=DEFAULT_BROWSER_HEADERS,
                impersonate='chrome',
                timeout=timeout,
            )
            if response.status_code == 200 and is_pdf_bytes(response.content):
                logger.info(f"Successfully downloaded full-card PDF ({len(response.content)} bytes)")
                return response.content
            logger.warning(
                "curl_cffi full-card download failed with status %s and content type %s",
                response.status_code,
                response.headers.get('Content-Type'),
            )
        except Exception as e:
            logger.warning(f"curl_cffi full-card download error: {e}")

    try:
        logger.info(f"Attempting full-card PDF for {track_code} {race_date} via requests")
        response = requests.get(url, headers=DEFAULT_BROWSER_HEADERS, timeout=timeout)
        if response.status_code == 200 and is_pdf_bytes(response.content):
            logger.info(f"requests recovered full-card PDF ({len(response.content)} bytes)")
            return response.content
        logger.warning(
            "requests full-card download failed with status %s and content type %s",
            response.status_code,
            response.headers.get('Content-Type'),
        )
    except Exception as e:
        logger.warning(f"requests full-card download error: {e}")

    content = download_pdf_via_powershell(url, timeout=timeout)
    if content:
        logger.info(f"Recovered full-card PDF for {track_code} {race_date} via pwsh")
        return content

    content = download_pdf_via_selenium(url, timeout=timeout)
    if content:
        logger.info(f"Recovered full-card PDF for {track_code} {race_date} via selenium cookies")
        return content

    return None


def download_pdf(pdf_url: str, timeout: int = 40) -> Optional[bytes]:
    """
    Download PDF from Equibase using PowerShell with robust browser masquerading to bypass WAF
    Returns: PDF bytes or None if download fails
    """
    logger.info(f"Downloading PDF from {pdf_url} using layered fallbacks")

    lightweight_downloaders = (
        download_pdf_via_curl_cffi,
        download_pdf_via_cloudscraper,
        download_pdf_via_requests,
    )
    heavy_downloaders = (
        download_pdf_via_powershell,
        download_pdf_via_selenium,
    )

    for downloader in lightweight_downloaders:
        content = downloader(pdf_url, timeout=timeout)
        if content:
            return content

    for downloader in heavy_downloaders:
        content = downloader(pdf_url, timeout=timeout)
        if content:
            return content

    logger.warning(f"All static PDF download methods failed for {pdf_url}")
    return None


def parse_equibase_pdf(pdf_bytes: bytes) -> Optional[Dict]:
    """
    Parse Equibase race chart PDF (Single Race or First Race of Full Card)
    Returns: Extracted race data or None if parsing fails
    """
    results = parse_equibase_full_card(pdf_bytes)
    return results[0] if results else None


def parse_equibase_full_card(pdf_bytes: bytes) -> List[Dict]:
    """
    Parse a "Full Card" Equibase PDF containing multiple races
    Returns: List of race data dicts
    """
    all_races = []
    try:
        if not pdf_bytes.startswith(b'%PDF'):
            logger.warning("Content is not a valid PDF")
            return []

        pdf_file = BytesIO(pdf_bytes)

        with pdfplumber.open(pdf_file) as pdf:
            current_race_pages = []
            
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                
                # Detect if this is a NEW race header
                # A new race chart usually starts with something containing "Race N" at the top
                # We saw patterns like "GULFSTREAMPARK-January9,2026-Race1 ?"
                is_header = False
                header_match = re.search(r'Race\s*(\d+)', text[:100], re.IGNORECASE)
                if header_match:
                    is_header = True
                
                if is_header:
                    # If we have collected pages for a race, parse them
                    if current_race_pages:
                        race_data = parse_pages_as_race(current_race_pages)
                        if race_data:
                            all_races.append(race_data)
                    current_race_pages = [page]
                else:
                    # Continuation page for the current race
                    if current_race_pages:
                        current_race_pages.append(page)
                    else:
                        # First page of PDF might not have the header if it's messy, but usually does
                        current_race_pages = [page]
            
            # Parse the final race
            if current_race_pages:
                race_data = parse_pages_as_race(current_race_pages)
                if race_data:
                    all_races.append(race_data)

    except Exception as e:
        logger.error(f"Error parsing full card PDF: {e}")
        
    return all_races


def parse_pages_as_race(pages: List) -> Optional[Dict]:
    """Helper to parse a group of pages representing one race"""
    try:
        # Combine text from all pages
        full_text = ""
        for page in pages:
            full_text += (page.extract_text() or "") + "\n"
        
        if not full_text:
            return None
            
        # Parse metadata from full text
        race_data = parse_race_chart_text(full_text)
        
        # Combine tables from all pages
        all_tables = []
        for page in pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
        
        horses = []
        if all_tables:
            horses = parse_horse_table(all_tables, full_text)
            
        if not horses:
            horses = parse_horses_from_text(full_text)
            
        if horses:
            # Payouts and scratches are usually on the primary page (first page of race)
            # but we use full_text now so it should find them
            wps_payouts = parse_wps_payouts(full_text)
            trainers_map = parse_trainers_section(full_text)
            
            for horse in horses:
                pgm = horse.get('program_number')
                if pgm and pgm in wps_payouts:
                    payout = wps_payouts[pgm]
                    horse['win_payout'] = payout.get('win')
                    horse['place_payout'] = payout.get('place')
                    horse['show_payout'] = payout.get('show')
                
                if not horse.get('trainer') and pgm and pgm in trainers_map:
                     horse['trainer'] = trainers_map[pgm]
            
            race_data['horses'] = horses
            
        return race_data
    except Exception as e:
        logger.error(f"Error parsing pages as race: {e}")
        return None



def parse_race_chart_text(text: str) -> Dict:
    """
    Parse race metadata from chart text
    """
    data = {
        'track_name': None,
        'race_date': None,
        'race_number': None,
        'post_time': None,
        'surface': None,
        'distance': None,
        'race_type': None,
        'conditions': None,
        'purse': None,
        'final_time': None,
        'fractional_times': [],
        'horses': [],
        'exotic_payouts': [],
        'wps_payouts': parse_wps_payouts(text),
        'exotic_payouts': [],
        'wps_payouts': parse_wps_payouts(text),
        'claims': [],
        'scratches': parse_scratched_horses(text)
    }

    lines = text.split('\n')

    # Extract track name (usually on first line)
    # SANITIZATION: Check if line 0 looks like a valid track name
    # It shouldn't contain "Race", digits, or be extremely long
    if lines:
        raw_name = lines[0].strip()
        
        is_suspicious = False
        if len(raw_name) > 50: is_suspicious = True
        if re.search(r'Race\s*\d+', raw_name, re.IGNORECASE): is_suspicious = True
        if re.search(r'\d{4}', raw_name): is_suspicious = True # Year
        
        # Check against common track map (expanded)
        known_tracks = {
            'AQUEDUCT': 'Aqueduct',
            'BELMONT': 'Belmont Park',
            'SARATOGA': 'Saratoga',
            'DEL MAR': 'Del Mar',
            'SANTA ANITA': 'Santa Anita Park',
            'GULFSTREAM': 'Gulfstream Park',
            'KEENELAND': 'Keeneland',
            'CHURCHILL': 'Churchill Downs',
            'TAMPA BAY': 'Tampa Bay Downs',
            'OAKLAWN': 'Oaklawn Park',
            'FAIR GROUNDS': 'Fair Grounds',
            'WOODBINE': 'Woodbine',
            'LAUREL': 'Laurel Park',
            'PIMLICO': 'Pimlico',
            'MONMOUTH': 'Monmouth Park',
            'PARX': 'Parx Racing',
            'PENN NATIONAL': 'Penn National',
            'MAHONING': 'Mahoning Valley Race Course',
            'TURF PARADISE': 'Turf Paradise',
            'GOLDEN GATE': 'Golden Gate Fields',
            'SAM HOUSTON': 'Sam Houston Race Park',
            'DELTA DOWNS': 'Delta Downs',
            'CHARLES TOWN': 'Charles Town',
            'FINGER LAKES': 'Finger Lakes',
            'HAWTHORNE': 'Hawthorne',
            'HORSESHOE INDIANAPOLIS': 'Horseshoe Indianapolis',
            'LOUISIANA DOWNS': 'Louisiana Downs',
            'PRAIRIE MEADOWS': 'Prairie Meadows',
            'PRESQUE ISLE': 'Presque Isle Downs',
            'REMINGTON': 'Remington Park',
            'RUIDOSO': 'Ruidoso Downs',
            'SUNLAND': 'Sunland Park',
            'TURFWAY': 'Turfway Park',
            'WILL ROGERS': 'Will Rogers Downs',
            'ZIA PARK': 'Zia Park'
        }
        
        clean_name = None
        upper_raw = raw_name.upper()
        
        # 1. Try to match known tracks
        for key, val in known_tracks.items():
            if key in upper_raw:
                clean_name = val
                break
                
        # 2. If no match but not suspicious, use raw
        if not clean_name and not is_suspicious:
            clean_name = raw_name
            
        # 3. If suspicious and no match, try next line? 
        # Or just return None and let caller fallback to Track Code
        if not clean_name and is_suspicious:
            logger.warning(f"Suspicious track name found in PDF: '{raw_name}'. ignoring.")
            data['track_name'] = None
        else:
             data['track_name'] = clean_name


    # Extract race number
    race_num_match = re.search(r'RACE\s+(\d+)', text, re.IGNORECASE)
    if race_num_match:
        data['race_number'] = int(race_num_match.group(1))
    else:
        # Try alternate format
        race_num_match = re.search(r'Race\s*#?\s*(\d+)', text, re.IGNORECASE)
        if race_num_match:
            data['race_number'] = int(race_num_match.group(1))

    # Extract date
    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
    if date_match:
        data['race_date'] = date_match.group(1)

    # Extract post time
    time_match = re.search(r'POST TIME:\s*(\d{1,2}:\d{2})', text, re.IGNORECASE)
    if time_match:
        data['post_time'] = time_match.group(1)

    # Extract surface
    for keyword in ['Dirt', 'Turf', 'All Weather', 'Synthetic']:
        if keyword in text:
            data['surface'] = keyword
            break

    # Extract distance
    dist_match = re.search(r'(\d+\s*(?:Furlongs?|Miles?|Yards?))', text, re.IGNORECASE)
    if dist_match:
        data['distance'] = dist_match.group(1)
    else:
        # Try fractional distance
        dist_match = re.search(r'(\d+\s*1/\d+\s*(?:Miles?|Furlongs?))', text, re.IGNORECASE)
        if dist_match:
            data['distance'] = dist_match.group(1)

    # Extract purse
    purse_match = re.search(r'PURSE[:\s]+\$?([\d,]+)', text, re.IGNORECASE)
    if purse_match:
        data['purse'] = f"${purse_match.group(1)}"

    # Extract race type
    for race_type in ['Claiming', 'Allowance', 'Maiden', 'Stakes', 'Handicap']:
        if race_type.lower() in text.lower():
            data['race_type'] = race_type
            break

    # Extract final time
    # More flexible regex to catch cases without colons, different separators, or missing spaces
    # Fix for cases like "Final Time : 1:44.23" or "Final Time: 1:44.23"
    time_match = re.search(r'FINAL\s*TIME\s*:?\s*([\d:.]+)', text, re.IGNORECASE)
    if time_match:
        data['final_time'] = time_match.group(1).strip()

    # Extract fractional times
    frac_match = re.findall(r'(\d+\.\d+)', text)
    if len(frac_match) > 0:
        # Filter to reasonable fractional times (between 20-70 seconds usually)
        data['fractional_times'] = [t for t in frac_match if 20.0 < float(t) < 70.0][:4]

    # Extract claims
    data['claims'] = parse_claims_text(text)

    return data


def parse_horse_table(tables: List, full_text: str) -> List[Dict]:
    """
    Parse horse entries from extracted PDF tables
    """
    horses = []

    # Find the largest table (usually the results table)
    if not tables:
        return horses

    main_table = max(tables, key=lambda t: len(t) if t else 0)

    if not main_table or len(main_table) < 2:
        logger.warning("No valid table found for horses")
        return horses

    # Try to identify columns
    header_row = main_table[0] if main_table else []
    logger.debug(f"Table header: {header_row}")
    
    num_cols = len(header_row)
    combined_rows = list(main_table[1:])
    
    # Merge continuation tables that might be on the next page
    for t in tables:
        if t == main_table or not t:
            continue
        # Check if table matches column count closely (+/- 1 column)
        if abs(len(t[0]) - num_cols) <= 1:
            for row in t:
                row_str = " ".join([str(c) for c in row if c]).lower()
                # Skip header rows in continuation tables
                if "horse" in row_str and ("jockey" in row_str or "pgm" in row_str):
                    continue
                combined_rows.append(row)

    # Process each row
    row_idx = 1
    for row in combined_rows:
        if not row or len(row) < 3:
            continue

        try:
            horse_data = {
                'program_number': normalize_pgm(str(row[0]).strip() if row[0] else str(row_idx)),
                'horse_name': str(row[1]).strip() if len(row) > 1 and row[1] else None,
                'jockey': str(row[2]).strip() if len(row) > 2 and row[2] else None,
                'trainer': str(row[3]).strip() if len(row) > 3 and row[3] else None,
                'owner': None,
                'weight': None,
                'odds': str(row[4]).strip() if len(row) > 4 and row[4] else None,
                'finish_position': row_idx,  # Assume order is finish position
                'comments': None,
                'speed_figure': None,
                'win_payout': None,
                'place_payout': None,
                'show_payout': None
            }
            
            # Check for scratched indications in the row
            row_str = " ".join([str(c) for c in row if c]).lower()
            if "scratched" in row_str or "scr" in row_str.split():
                 logger.info(f"Skipping scratched horse in table: {horse_data['horse_name']}")
                 continue
            
            # GARBAGE FILTER: Check if name is a known metadata label
            name_check = horse_data['horse_name'].lower()
            garbage_terms = ['preliminary', 'mutuel', 'total', 'wps', 'claiming', 'footnote', 'winner', 'final time']
            if any(term in name_check for term in garbage_terms):
                logger.info(f"Skipping garbage row matching metadata term: {horse_data['horse_name']}")
                continue
            
            # Helper to merge WPS if available
            # Note: We can't access race_data here directly easily unless we pass it or pass payouts map
            # TODO: We need to refactor parse_horse_table signature or do the merge later.
            # Actually, let's fix the call site, but for now we need to enable "payouts" arg in this function?
            # Or we can do it after this function returns in parse_equibase_pdf
            # Let's check parse_equibase_pdf again.


            # Clean up horse name
            if horse_data['horse_name']:
                horse_data['horse_name'] = re.sub(r'[^\w\s\'-]', '', horse_data['horse_name'])

            if horse_data['horse_name']:
                horses.append(horse_data)

        except Exception as e:
            logger.debug(f"Error parsing row {row_idx}: {e}")
            
        row_idx += 1

    logger.info(f"Parsed {len(horses)} horses from table")
    return horses


def parse_horses_from_text(text: str) -> List[Dict]:
    """
    Fallback parser for horse data from raw text when table extraction fails
    Expects format: LastRaced Pgm HorseName(Jockey) ...
    """
    horses = []
    lines = text.split('\n')
    
    start_parsing = False
    
    # Regex to capture: Pgm, HorseName, Jockey, (skip), Odds
    # Example: 20Nov255AQU2 1 Coquito(Carmouche,Kendrick) 123 Lb ... 0.48* chased3w,edgedclear
    # We look for Pgm (number), Name(Jockey), and Odds (decimal at end)
    pattern = re.compile(r'^\s*\S+\s+(\d+)\s+([^(]+)\(([^)]+)\).*?(\d+\.\d+\*?)\s+')
    
    for line in lines:
        # Detect header
        if 'HorseName(Jockey)' in line or 'Horse Name (Jockey)' in line:
            start_parsing = True
            continue
            
        if not start_parsing:
            continue
            
        # Stop parsing if we hit other sections
        if 'Fractional Times' in line or 'Final Time' in line or 'Run-Up' in line or line.strip() == '':
            if len(horses) > 0: # If we already found horses, stop
                break
        
        match = re.search(pattern, line)
        if match:
            try:
                pgm = match.group(1)
                horse_name = match.group(2).strip()
                jockey = match.group(3).strip()
                odds = match.group(4).replace('*', '')
                
                horses.append({
                    'program_number': pgm,
                    'horse_name': horse_name,
                    'jockey': jockey,
                    'trainer': None, # Difficult to parse from this line
                    'owner': None,
                    'weight': None,
                    'odds': odds,
                    'finish_position': len(horses) + 1,
                    'comments': None,
                    'speed_figure': None,
                    'win_payout': None,
                    'place_payout': None,
                    'show_payout': None
                })
            except Exception as e:
                logger.debug(f"Regex match error on line '{line}': {e}")
                continue

    logger.info(f"Parsed {len(horses)} horses from text fallback")
    return horses


def parse_exotic_payouts(text: str) -> List[Dict]:
    """
    Extract exotic wager payouts from chart text
    """
    payouts = []

    # Common exotic bet patterns
    patterns = {
        'Exacta': r'EXACTA.*?\$?([\d,]+\.\d{2})',
        'Trifecta': r'TRIFECTA.*?\$?([\d,]+\.\d{2})',
        'Superfecta': r'SUPERFECTA.*?\$?([\d,]+\.\d{2})',
        'Daily Double': r'DAILY DOUBLE.*?\$?([\d,]+\.\d{2})',
        'Pick 3': r'PICK 3.*?\$?([\d,]+\.\d{2})',
        'Pick 4': r'PICK 4.*?\$?([\d,]+\.\d{2})',
    }

    for wager_type, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            payouts.append({
                'wager_type': wager_type,
                'payout': float(match.group(1).replace(',', '')),
                'winning_combination': None  # Would need more parsing
            })

    return payouts


def parse_wps_payouts(text: str) -> Dict[str, Dict[str, float]]:
    """
    Parse Win/Place/Show payouts from the 'Mutuel Prices' or 'Payoffs' section
    Returns: Dict mapping Program Number -> {'win': float, 'place': float, 'show': float}
    """
    payouts = {}
    
    # 1. Find the start of the section
    # Usually "Total WPS Pool" or headers "Pgm Horse Win Place Show"
    lines = text.split('\n')
    start_idx = -1
    
    header_pattern = re.compile(r'Pgm\s+Horse\s+Win\s+Place\s+Show', re.IGNORECASE)
    
    for i, line in enumerate(lines):
        if header_pattern.search(line):
            start_idx = i + 1
            break
            
    if start_idx == -1:
        # Try finding "Total WPS Pool" then look ahead a line or two
        pool_pattern = re.compile(r'Total\s+WPS\s+Pool', re.IGNORECASE)
        for i, line in enumerate(lines):
            if pool_pattern.search(line):
                # Header usually follows or is nearby
                # Scan next few lines for header? Or assuming next lines are data if header is missing/implicit
                # Let's try to assume data follows immediately after header row found by context
                pass # Logic difficult without consistent header, but header is standard on Equibase
    
    if start_idx == -1:
        logger.debug("Could not find WPS Payouts section header")
        return payouts
        
    # 2. Parse the rows following the header
    # We expect rows roughly ordered by finish position:
    # Row 1 (Winner): Pgm Name Win Place Show
    # Row 2 (Place): Pgm Name Place Show
    # Row 3 (Show): Pgm Name Show
    
    # Regex to extract: Pgm (digits/char), Horse Name (text), Floats...
    # The complexity is that Horse Name can contain spaces.
    # But Pgm is at start, and floats are at end (sort of, WagerType might follow).
    
    # Strategy: Find all prices (Pattern: \d+\.\d{2})
    # Then everything before the first price is Pgm + Horse Name
    
    current_row_idx = 0 # 0=Win/Place/Show, 1=Place/Show, 2=Show
    
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
            
        # Stop condition: Section end? 
        # Usually followed by "Past Performance" or "Footnotes" or empty lines
        if "Past Performance" in line or "Footnotes" in line or "Trainers:" in line:
            break
            
        # Stop if we hit Exotics (sometimes on same line, sometimes next)
        # Actually in the screenshot, "Wager Type" is on the SAME LINE as the first horse
        # But `extract_text` might separate them or keep them.
        # We process the line assuming it effectively starts with Pgm ... Prices
        
        # Regex for prices: look for numbers like "15.60"
        # Note: sometimes they are just "4.20"
        prices = re.findall(r'(\d+\.\d{2})', line)
        
        if not prices:
            continue
            
        # Pgm is usually the first token
        parts = line.split()
        if not parts:
            continue
            
        pgm = parts[0]
        
        # Validate Pgm is somewhat short (e.g. "1", "1A", "10")
        if len(pgm) > 4: 
            continue
            
        # Map prices based on row index logic
        # Note: This is a heuristics based on standard Finish Order sorting in the table
        
        win_val = None
        place_val = None
        show_val = None
        
        # Extract potential prices. 
        # We need to distinguish "Prices" from "Pools" or "Payoffs" of exotics if they appear on the same line.
        # In the screenshot: 
        # Line 1: 3 Daylan 15.60 8.00 5.00 $1.00 Exacta...
        # Prices are 15.60, 8.00, 5.00, 1.00 (wager), 125.80 (payoff)
        # We must take the FIRST 1, 2, or 3 prices that appear textually before "Wager Type" or end of line.
        
        # Refined regex: Split line by the first occurrence of known Wager Types? 
        # Or just take the first N floats found?
        # Usually Pgm Name P1 P2 P3 ...
        
        # Let's try to isolate the "WPS" part.
        # It ends before "Wager Type" column start.
        # But we don't know column positions in raw text.
        
        # Heuristic: 
        # - Row 0 (Winner): Expect 3 prices (Win, Place, Show). If fewer, maybe dead heat or missing data.
        # - Row 1 (Place): Expect 2 prices (Place, Show).
        # - Row 2 (Show): Expect 1 price (Show).
        
        # Filter prices to only those that look like WPS prices? No distinguishing feature.
        # Take the first k valid floats found in the line.
        
        try:
            # We assume the first found prices correspond to Win/Place/Show columns depending on row
            
            valid_prices = []
            # We iterate matches. We stop if we hit something that looks like an exotic bet amount (usually prefixed by $) or Wager Name
            # Actually, raw text might imply spatial separation.
            
            # Let's iterate tokens to be safer?
            # "3", "Daylan", "15.60", "8.00", "5.00", "$1.00", "Exacta"...
            
            # Find the index where prices start
            price_start_idx = -1
            found_prices = []
            
            tokens = line.split()
            for idx, token in enumerate(tokens):
                # skip pgm
                if idx == 0: continue
                
                # Check if price
                # handling "$15.60" or "15.60"
                clean_token = token.replace('$', '')
                if re.match(r'^\d+\.\d{2}$', clean_token):
                     found_prices.append(float(clean_token))
                elif token.startswith('$'): 
                     # Should be start of Wager Type section e.g. $1.00 Exacta
                     # Stop collecting prices
                     break
                elif re.match(r'Exacta|Trifecta|Superfecta|Daily|Pick', token, re.IGNORECASE):
                     break
            
            row_payouts = {'win': None, 'place': None, 'show': None}
            
            if current_row_idx == 0: # Winner row
                # Expect 3 prices (Win, Place, Show)
                if len(found_prices) >= 3:
                    row_payouts['win'] = found_prices[0]
                    row_payouts['place'] = found_prices[1]
                    row_payouts['show'] = found_prices[2]
                elif len(found_prices) == 2: # Maybe no show betting? Or Dead Heat?
                    row_payouts['win'] = found_prices[0]
                    row_payouts['place'] = found_prices[1]
                elif len(found_prices) == 1:
                    row_payouts['win'] = found_prices[0]
                    
            elif current_row_idx == 1: # Place row
                # Expect Place, Show
                if len(found_prices) >= 2:
                    row_payouts['place'] = found_prices[0]
                    row_payouts['show'] = found_prices[1]
                elif len(found_prices) == 1:
                    row_payouts['place'] = found_prices[0]
                    
            elif current_row_idx >= 2: # Show row(s)
                # Expect Show
                if len(found_prices) >= 1:
                    row_payouts['show'] = found_prices[0]
                    # Note: if there's a dead heat for 3rd, there might be multiple lines here
            
            if any(row_payouts.values()):
                payouts[pgm] = row_payouts
                current_row_idx += 1
                
        except Exception as e:
            logger.debug(f"Error parsing WPS line '{line}': {e}")
            continue
    return payouts



def parse_trainers_section(text: str) -> Dict[str, str]:
    """
    Parse Trainers section from text
    Example: Trainers: 3 - Handal, Raymond; 4 - Rice, Linda; ...
    """
    trainers = {}
    
    # Locate section
    # Regex: Trainers:\s*(.*?)(?:\s+Owners:|\s+Footnotes|\s+Scratched|$)
    match = re.search(r'Trainers:\s*(.*?)(?:\s+Owners:|\s+Footnotes|\s+Scratched|$)', text, re.IGNORECASE | re.DOTALL)
    
    if match:
        content = match.group(1).replace('\n', ' ').strip()
        # Split by semicolon
        # entry format: "Pgm - Name"
        entries = content.split(';')
        for entry in entries:
            entry = entry.strip()
            if not entry: continue
            
            # Split by " - " or just "-"
            parts = entry.split('-', 1)
            if len(parts) == 2:
                pgm = parts[0].strip()
                name = parts[1].strip()
                trainers[pgm] = name
            else:
                # Fallback: maybe space separated? "3 Handal, Raymond"
                # Check for first digit
                m = re.match(r'^(\d+)\s+(.+)', entry)
                if m:
                    trainers[m.group(1)] = m.group(2).strip()
                    
    return trainers


def parse_scratched_horses(text: str) -> List[str]:
    """
    Parse Scratched Horses section
    Example: Scratched Horse(s): Horse Name (Reason)
    """
    scratches = []
    # Expanded stop tokens to prevent runaway captures
    stop_pattern = r'(?:\s+Trainers:|\s+Owner\(s\):|\s+Footnotes|\s+Claiming|\s+Total\s*WPS|\s+Pgm\s+Horse|\s+Claiming\s*Prices|\s+Mutuel\s+Prices|\s+Winner:|\s+Final\s+Time|$)'
    
    match = re.search(r'Scratched\s*Horse\(s\)\s*:\s*(.*?)' + stop_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        content = match.group(1).replace('\n', ' ').strip()
        
        # Split by semicolon or comma
        parts = re.split(r'[;,]\s*', content)
        
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # Remove reason in parens "(Trainer)" and other noise
            name = re.sub(r'\s*\(.*?\)', '', part).strip()
            
            # Filter matches
            # 1. Must rename valid after normalization
            norm = normalize_name(name)
            if not norm or len(norm) < 3:
                continue
                
            # 2. Heuristic: Name shouldn't be too long (unlikely > 30 chars for a horse name)
            if len(name) > 35:
                continue

            if name:
                scratches.append(name)
                
    return scratches


def parse_claims_text(text: str) -> List[Dict]:
    """
    Parse claimed horses information
    Example: 1 Claimed Horse(s): Coquito New Trainer: Linda Rice New Owner: Linda Rice
    Also handles multi-line claims and split labels.
    """
    claims = []
    lines = text.split('\n')
    
    # 1. Parse Claiming Prices first to get price map
    price_map = {}
    
    # Flexible regex: Claiming\s*Prices\s*:
    price_match = re.search(r'Claiming\s*Prices\s*:(.*?)(?:Scratched|Total|Footnotes|$)', text, re.DOTALL | re.IGNORECASE)
    if price_match:
        price_text = price_match.group(1).strip()
        # Split by semicolon or just find all matches
        # Pattern: number - Name: $price (Allow space after $)
        price_items = re.findall(r'(\d+)\s*-\s*([^:]+):\s*\$\s*([\d,]+)', price_text)
        for num, name, price in price_items:
            # Normalize name
            norm_name = normalize_name(name)
            price_val = float(price.replace(',', ''))
            price_map[norm_name] = price_val
            logger.debug(f"Mapped '{name}' (norm: {norm_name}) to {price_val}")

    # 2. Parse Claimed Horse lines using robust state machine
    in_claims = False
    current_claim = None
    
    # Patterns
    # Note: (\s*) allows for no space if PDF extraction removed it
    trainer_pat = re.compile(r'\s*(?:New\s*Trainer|NewTrainer)\s*:\s*', re.IGNORECASE)
    owner_pat = re.compile(r'\s*(?:New\s*Owner|NewOwner)\s*:\s*', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Start detection
        if re.search(r'Claimed\s*Horse\(s\)\s*:', line, re.IGNORECASE):
            in_claims = True
            # Remove the prefix "N Claimed Horse(s):" to process the first line content
            line = re.sub(r'^\d*\s*Claimed\s*Horse\(s\)\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            
        if not in_claims: continue
        
        # End detection
        # Stop at ClaimingPrices, Scratched, Total, Fractional, Final Time, Run-Up match
        if re.match(r'(Claiming\s*Prices|Scratched|Total|Fractional|Final|Run-Up)', line, re.IGNORECASE):
            if current_claim: claims.append(current_claim)
            in_claims = False
            break
            
        # Process Line Logic
        # Check if line contains "New Trainer" -> Starts a new claim
        trainer_match = trainer_pat.search(line)
        
        if trainer_match:
            # Save previous claim if valid
            if current_claim: claims.append(current_claim)
            
            # This line starts a new claim
            # Format: "HorseName NewTrainer: TrainerName [NewOwner: OwnerName]"
            
            # Split at Trainer label
            start_idx = trainer_match.start()
            end_idx = trainer_match.end()
            
            horse_part = line[:start_idx].strip()
            rest = line[end_idx:].strip()
            
            # Now search for Owner in 'rest'
            owner_match = owner_pat.search(rest)
            
            if owner_match:
                # "TrainerName NewOwner: OwnerName"
                o_start = owner_match.start()
                o_end = owner_match.end()
                
                trainer_name = rest[:o_start].strip()
                owner_name = rest[o_end:].strip()
                
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': trainer_name,
                    'new_owner': owner_name,
                    'claim_price': None
                }
            else:
                # "TrainerName [maybe crap]" or partial line
                # Treat rest as trainer name provisionally
                current_claim = {
                    'horse_name': horse_part,
                    'new_trainer': rest, 
                    'new_owner': ""
                }
        else:
            # No "New Trainer". Continuation line.
            if current_claim:
                # Identify if previous line ended with partial label like "NewOw"
                prev_trainer = current_claim['new_trainer']
                
                # Check for "NewOwner" reconstruction from split label
                if prev_trainer.endswith("NewOw") or prev_trainer.endswith("New"):
                     # Attempt to combine and re-check owner pattern
                     combined = prev_trainer + line
                     om = owner_pat.search(combined)
                     if om:
                         o_start = om.start()
                         o_end = om.end()
                         
                         real_trainer = combined[:o_start].strip()
                         real_owner = combined[o_end:].strip()
                         
                         current_claim['new_trainer'] = real_trainer
                         current_claim['new_owner'] = real_owner
                     else:
                         # Just append to owner if we already had one, or append to trainer?
                         # If we didn't have an owner, and this doesn't match owner pattern, it might be trailing trainer name?
                         if not current_claim['new_owner']:
                             current_claim['new_trainer'] += " " + line
                         else:
                             current_claim['new_owner'] += " " + line
                else:
                    # Normal continuation
                    if not current_claim['new_owner']:
                        # Maybe we missed the owner label or it's coming
                        # Or maybe the trainer name is long?
                        # Usually "New Owner" follows trainer.
                        # If we haven't seen New Owner label yet, and this line doesn't have it...
                        # Check if this line IS the owner label?
                        om = owner_pat.search(line)
                        if om:
                             o_end = om.end()
                             owner_name = line[o_end:].strip()
                             current_claim['new_owner'] = owner_name
                        else:
                             # Append to trainer
                             current_claim['new_trainer'] += " " + line
                    else:
                        # Append to owner
                        current_claim['new_owner'] += " " + line
                        current_claim['new_owner'] = current_claim['new_owner'].strip()

    # Final cleanup and pricing
    for c in claims:
        # Match price
        hn = normalize_name(c['horse_name'])
        price = price_map.get(hn)
        if not price:
            # Fuzzy match
            for k, v in price_map.items():
                if k in hn or hn in k:
                    price = v
                    break
        c['claim_price'] = price
        
        # Clean specific artifacts
        if c['new_owner']: c['new_owner'] = c['new_owner'].strip()
        if c['new_trainer']: c['new_trainer'] = c['new_trainer'].strip()

    return claims


def extract_race_from_pdf(
    pdf_url: str,
    max_retries: int = 3,
    cached_full_card_races: Optional[Dict[int, Dict]] = None,
) -> Optional[Dict]:
    """
    Extract race data from Equibase PDF using local parsing
    Returns: Extracted race data or None if extraction fails
    """
    fallback_meta = parse_equibase_static_pdf_url(pdf_url)
    if fallback_meta and cached_full_card_races:
        cached_race = cached_full_card_races.get(fallback_meta[2])
        if cached_race and cached_race.get('horses'):
            logger.info(
                "Using cached full-card race %s for %s",
                fallback_meta[2],
                fallback_meta[0],
            )
            return cached_race

    for attempt in range(1, max_retries + 1):
        logger.info(f"Extracting data from {pdf_url} (attempt {attempt}/{max_retries})")

        # Download PDF
        pdf_bytes = download_pdf(pdf_url)
        race_data = None

        if not pdf_bytes:
            logger.warning(f"Extraction attempt {attempt} failed: Could not download PDF")
        else:
            # Parse PDF
            race_data = parse_equibase_pdf(pdf_bytes)
            del pdf_bytes
            if race_data and race_data.get('horses'):
                logger.info(f"Successfully extracted race with {len(race_data['horses'])} horses")
                return race_data
            logger.warning(f"Extraction attempt {attempt} failed: Could not parse race data")

        if fallback_meta:
            track_code, race_date, race_number = fallback_meta
            logger.info(
                "Attempting full-card fallback for %s Race %s on %s",
                track_code,
                race_number,
                race_date,
            )
            full_card_map = cached_full_card_races
            if not full_card_map:
                full_card_pdf = download_full_card_pdf(track_code, race_date)
                if full_card_pdf:
                    try:
                        full_card_map = build_race_map(parse_equibase_full_card(full_card_pdf))
                        del full_card_pdf
                    except Exception as e:
                        logger.error(f"Full-card fallback parse failed: {e}")
                        full_card_map = None
            if full_card_map:
                try:
                    matched_race = full_card_map.get(race_number)
                    if matched_race:
                        logger.info(
                            f"Recovered {track_code} Race {race_number} from full-card fallback "
                            f"with {len(matched_race.get('horses', []))} horses"
                        )
                        return matched_race
                    logger.warning(
                        f"Full-card fallback did not contain a parsable race {race_number} for {track_code}"
                    )
                except Exception as e:
                    logger.error(f"Full-card fallback parse failed: {e}")

        if attempt < max_retries:
            gc.collect()
            time.sleep(2 * attempt)

    logger.error(f"All extraction attempts failed for {pdf_url}")
    return None


def get_or_create_track(supabase, track_code: str, track_name: str = None) -> Optional[int]:
    """Get track ID or create if doesn't exist"""
    try:
        # Try to find existing track
        result = supabase.table('hranalyzer_tracks').select('id').eq('track_code', track_code).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]['id']

        # Create new track
        new_track = {
            'track_code': track_code,
            'track_name': track_name or track_code,
            'location': None,
            'timezone': 'America/New_York'
        }

        result = supabase.table('hranalyzer_tracks').insert(new_track).execute()
        if result.data:
            logger.info(f"Created new track: {track_code}")
            return result.data[0]['id']

        return None

    except Exception as e:
        logger.error(f"Error getting/creating track: {e}")
        return None


def insert_race_to_db(supabase, track_code: str, race_date: date, race_data: Dict, race_number: int = None) -> bool:
    """
    Insert crawled race data into Supabase
    Returns: True if successful, False otherwise
    """
    try:
        # Get or create track
        track_id = get_or_create_track(supabase, track_code, race_data.get('track_name'))
        if not track_id:
            logger.error(f"Could not get track_id for {track_code}")
            return False

        # Build race key - Priority: 1. Passed race_number, 2. Data from PDF, 3. Default 1
        if race_number is None:
            race_number = race_data.get('race_number', 1)
            
        race_key = f"{track_code}-{race_date.strftime('%Y%m%d')}-{race_number}"

        # Find winner's program number
        winner_program_number = None
        if race_data.get('horses'):
            for h in race_data['horses']:
                # finish_position is usually int, but be safe
                if str(h.get('finish_position')) == '1':
                    winner_program_number = h.get('program_number')
                    break


        # Check if race already exists
        existing = supabase.table('hranalyzer_races').select('id').eq('race_key', race_key).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"Race {race_key} already exists, updating...")
            race_id = existing.data[0]['id']
            update_mode = True
        else:
            update_mode = False

        # Prepare race data
        race_insert = {
            'race_key': race_key,
            'track_id': track_id,
            'track_code': track_code,
            'race_date': race_date.strftime('%Y-%m-%d'),
            'race_number': race_number,
            'winner_program_number': winner_program_number,
            # 'post_time': race_data.get('post_time'), # Handle conditionally below
            'surface': race_data.get('surface'),
            'distance': race_data.get('distance'),
            'race_type': race_data.get('race_type'),
            'conditions': race_data.get('conditions'),
            'purse': race_data.get('purse'),
            'final_time': race_data.get('final_time'),
            'fractional_times': ', '.join(race_data.get('fractional_times', [])) if race_data.get('fractional_times') else None,
            'race_status': 'completed',
            'data_source': 'equibase',
            'equibase_pdf_url': build_equibase_url(track_code, race_date, race_number),
            'equibase_chart_url': build_equibase_url(track_code, race_date, race_number),
        }

        # Only update post_time if we actually found one
        if race_data.get('post_time'):
            race_insert['post_time'] = race_data.get('post_time')

        if update_mode:
            result = supabase.table('hranalyzer_races').update(race_insert).eq('id', race_id).execute()
        else:
            result = supabase.table('hranalyzer_races').insert(race_insert).execute()
            if result.data:
                race_id = result.data[0]['id']

        logger.info(f"{'Updated' if update_mode else 'Inserted'} race {race_key}")

        # Insert horses and entries
        horses_data = race_data.get('horses', [])
        updated_entry_ids = []
        
        if horses_data:
            for horse_data in horses_data:
                entry_id = insert_horse_entry(supabase, race_id, horse_data)
                if entry_id:
                    updated_entry_ids.append(entry_id)

        # ---------------------------------------------------------
        # ZOMBIE CLEANUP: Scratch entries that weren't updated
        # Only run when we have a full set of results (>= 3 finishers).
        # A partial PDF parse (e.g. only 1 horse extracted) must NOT wipe
        # out all the pre-existing upcoming entries for the race.
        # ---------------------------------------------------------
        zombie_scratches_marked = 0
        if updated_entry_ids and len(updated_entry_ids) >= 3:
            try:
                # 1. Fetch all active (non-scratched) entries for this race
                all_entries = supabase.table('hranalyzer_race_entries')\
                    .select('id, program_number, scratched')\
                    .eq('race_id', race_id)\
                    .execute()
                
                if all_entries.data:
                    for entry in all_entries.data:
                        # If entry is NOT in our update list, and NOT already scratched
                        if entry['id'] not in updated_entry_ids and not entry.get('scratched'):
                            logger.warning(f"Marking ZOMBIE entry as scratched: ID {entry['id']} (Pgm {entry['program_number']})")
                            
                            supabase.table('hranalyzer_race_entries')\
                                .update({'scratched': True, 'finish_position': None})\
                                .eq('id', entry['id'])\
                                .execute()
                            zombie_scratches_marked += 1
            except Exception as e:
                logger.error(f"Error during zombie cleanup: {e}")
        if zombie_scratches_marked:
            record_scratch_event(
                "results_pdf_inferred",
                {
                    "track_code": track_code,
                    "race_date": race_date.strftime('%Y-%m-%d'),
                    "race_number": race_number,
                    "changes_processed": zombie_scratches_marked,
                },
            )
        # ---------------------------------------------------------

        # Insert exotic payouts
        payouts = race_data.get('exotic_payouts', [])
        if payouts:
            for payout in payouts:
                insert_exotic_payout(supabase, race_id, payout)

        # Insert claims
        claims_data = race_data.get('claims', [])
        if claims_data:
            for claim in claims_data:
                insert_claim(supabase, race_id, claim)

        # Mark scratches
        scratches = race_data.get('scratches', [])
        if scratches:
            scratches_marked = mark_scratched_horses(supabase, race_id, scratches)
            if scratches_marked:
                record_scratch_event(
                    "results_pdf_declared",
                    {
                        "track_code": track_code,
                        "race_date": race_date.strftime('%Y-%m-%d'),
                        "race_number": race_number,
                        "changes_processed": scratches_marked,
                        "scratch_names": scratches,
                    },
                )

        return True

    except Exception as e:
        logger.error(f"Error inserting race to database: {e}")
        return False


def get_or_create_participant(supabase, table_name: str, name_col: str, name_val: str) -> Optional[str]:
    """Generic helper to get or create a named entity (Jockey, Trainer, etc)"""
    try:
        # Check existing
        res = supabase.table(table_name).select('id').eq(name_col, name_val).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['id']
        
        # Create new
        new_record = {name_col: name_val}
        res = supabase.table(table_name).insert(new_record).execute()
        if res.data:
            return res.data[0]['id']
            
    except Exception as e:
        logger.error(f"Error in get_or_create_participant for {table_name}: {e}")
    return None


def insert_horse_entry(supabase, race_id: int, horse_data: Dict) -> Optional[str]:
    """
    Insert horse and race entry
    Returns: Entry ID if successful, None otherwise
    """
    try:
        horse_name = horse_data.get('horse_name')
        if not horse_name:
            return None

        # CRITICAL VALIDITY CHECK
        pgm_check = normalize_pgm(horse_data.get('program_number'))
        if not pgm_check or pgm_check in ['0', '', 'None']:
            logger.warning(f"Skipping entry for {horse_name} - Invalid Program Number: '{horse_data.get('program_number')}'")
            return None

        # -------------------------------------------------------
        # CANONICAL NAME LOOKUP (Fuzzy Match / Race Constraint)
        # -------------------------------------------------------
        horse_id = None
        
        # 1. PRIORITY: Check existing entries for THIS race first!
        # This fixes "StayedinforHalf" (PDF) vs "Stayed in for Half" (Entry) split.
        # We prefer the existing Entry over a new global lookup/create.
        
        race_horses = supabase.table('hranalyzer_race_entries')\
            .select('horse_id, hranalyzer_horses(id, horse_name)')\
            .eq('race_id', race_id)\
            .execute()
            
        found_local_match = False
        if race_horses.data:
            norm_target = normalize_name(horse_name)
            candidates = []
            
            for entry in race_horses.data:
                db_horse = entry.get('hranalyzer_horses')
                if db_horse:
                    db_name = db_horse.get('horse_name')
                    if normalize_name(db_name) == norm_target:
                         candidates.append(db_horse)
            
            if candidates:
                 # Pick the best candidate (most spaces = most readable)
                 candidates.sort(key=lambda x: x['horse_name'].count(' '), reverse=True)
                 best_match = candidates[0]
                 horse_id = best_match['id']
                 found_local_match = True
                 logger.info(f"Smart matched '{horse_name}' to existing '{best_match['horse_name']}' in race entries.")

        # 2. Fallback: Standard Global Lookup if no local match
        if not found_local_match:
            # Try Exact Match
            horse_result = supabase.table('hranalyzer_horses').select('id').eq('horse_name', horse_name).execute()
            
            if horse_result.data and len(horse_result.data) > 0:
                horse_id = horse_result.data[0]['id']
            else:
                # Create new horse
                new_horse = {'horse_name': horse_name}
                horse_insert = supabase.table('hranalyzer_horses').insert(new_horse).execute()
                if horse_insert.data:
                    horse_id = horse_insert.data[0]['id']
                else:
                    logger.error(f"Could not create horse: {horse_name}")
                    return None

        # Get/Create Jockey
        jockey_id = None
        jockey_name = horse_data.get('jockey')
        if jockey_name:
            jockey_id = get_or_create_participant(supabase, 'hranalyzer_jockeys', 'jockey_name', jockey_name)

        # Get/Create Trainer
        trainer_id = None
        trainer_name = horse_data.get('trainer')
        if trainer_name:
            trainer_id = get_or_create_participant(supabase, 'hranalyzer_trainers', 'trainer_name', trainer_name)

        # Create race entry
        entry_data = {
            'race_id': race_id,
            'horse_id': horse_id,
            'program_number': normalize_pgm(horse_data.get('program_number')), # Normalize PGM here too
            'finish_position': horse_data.get('finish_position'),
            'jockey_id': jockey_id,
            'trainer_id': trainer_id,
            'final_odds': horse_data.get('odds'),
            'win_payout': horse_data.get('win_payout'),
            'place_payout': horse_data.get('place_payout'),
            'show_payout': horse_data.get('show_payout'),
            'run_comments': horse_data.get('comments'),
            'weight': horse_data.get('weight')
        }

        try:
            # Use upsert to handle case where entries were pre-populated by DRF PDF upload
            # on_conflict specified to match unique constraint (race_id, program_number)
            # scratched=False: restore any entries incorrectly marked scratched by zombie cleanup
            entry_data['scratched'] = False
            res = supabase.table('hranalyzer_race_entries').upsert(entry_data, on_conflict='race_id, program_number').execute()
            logger.debug(f"Upserted entry for horse {horse_name}")

            if res.data:
                return res.data[0]['id']

            # Supabase upsert may not return data in all versions — fall back to a direct lookup
            lookup = supabase.table('hranalyzer_race_entries')\
                .select('id')\
                .eq('race_id', entry_data['race_id'])\
                .eq('program_number', entry_data['program_number'])\
                .execute()
            if lookup.data:
                return lookup.data[0]['id']

        except Exception as e:
            logger.error(f"Error upserting horse entry: {e}")
            
    except Exception as e:
        logger.error(f"Error inserting horse entry: {e}")
        
    return None


def insert_exotic_payout(supabase, race_id: int, payout_data: Dict):
    """Insert exotic payout"""
    try:
        payout_insert = {
            'race_id': race_id,
            'wager_type': payout_data.get('wager_type'),
            'winning_combination': payout_data.get('winning_combination'),
            'payout': payout_data.get('payout')
        }

        supabase.table('hranalyzer_exotic_payouts').insert(payout_insert).execute()
        logger.debug(f"Inserted {payout_data.get('wager_type')} payout")

    except Exception as e:
        logger.error(f"Error inserting exotic payout: {e}")


def insert_claim(supabase, race_id: int, claim_data: Dict):
    """Insert claim data"""
    try:
        horse_name = claim_data.get('horse_name')
        
        # Lookup program_number from race entries for this horse
        program_number = None
        try:
            entries = supabase.table('hranalyzer_race_entries')\
                .select('program_number, hranalyzer_horses(horse_name)')\
                .eq('race_id', race_id)\
                .execute()
            
            if entries.data:
                norm_claim = normalize_name(horse_name)
                for entry in entries.data:
                    db_horse = entry.get('hranalyzer_horses') or {}
                    db_name = db_horse.get('horse_name', '')
                    if normalize_name(db_name) == norm_claim:
                        program_number = entry.get('program_number')
                        break
        except Exception as e:
            logger.debug(f"Could not lookup program_number for claim: {e}")
        
        claim_insert = {
            'race_id': race_id,
            'horse_name': horse_name,
            'program_number': program_number,
            'new_trainer_name': claim_data.get('new_trainer'),
            'new_owner_name': claim_data.get('new_owner'),
            'claim_price': claim_data.get('claim_price')
        }
        
        # Use upsert to update existing claims (e.g. if price was missing)
        # Unique constraint is (race_id, horse_name)
        supabase.table('hranalyzer_claims').upsert(claim_insert, on_conflict='race_id, horse_name').execute()
        
        logger.info(f"Upserted claim for {horse_name} (Pgm #{program_number}) with price {claim_insert['claim_price']}")
        
    except Exception as e:
        logger.error(f"Error inserting/updating claim: {e}")


def mark_scratched_horses(supabase, race_id: int, scratched_names: List[str]) -> int:
    """
    Mark horses as scratched in the database
    """
    try:
        if not scratched_names:
            return 0

        # 1. Get all entries for this race to find program numbers/ids by name
        # We need to join with horses table to get names
        entries = supabase.table('hranalyzer_race_entries')\
            .select('id, program_number, hranalyzer_horses!inner(horse_name)')\
            .eq('race_id', race_id)\
            .execute()
            
        if not entries.data:
            return 0

        # 2. Match names with STRICTER logic
        scratches_marked = 0
        for name in scratched_names:
            norm_scratch = normalize_name(name)
            
            # Guard: If scratch name normalizes to empty/short string, SKIP IT.
            # This prevents "..." matching everyone.
            if len(norm_scratch) < 3:
                logger.warning(f"Skipping ambiguous scratch name: '{name}' (norm: '{norm_scratch}')")
                continue
            
            for entry in entries.data:
                h_name = entry['hranalyzer_horses']['horse_name']
                norm_h = normalize_name(h_name)
                
                match_found = False
                
                # 1. Exact Match (Best)
                if norm_scratch == norm_h:
                    match_found = True
                    
                # 2. One-way containment (Scratch is substring of Horse)
                # Only if scratch name is long enough to be unique
                elif len(norm_scratch) >= 4 and norm_scratch in norm_h:
                    match_found = True
                    
                # removed reverse containment (norm_h in norm_scratch) to prevent "Secretariat" matching "Secretariat's Son"
                
                if match_found:
                    # Set scratched=True
                    supabase.table('hranalyzer_race_entries')\
                        .update({'scratched': True, 'finish_position': None})\
                        .eq('id', entry['id'])\
                        .execute()
                    
                    logger.info(f"Marked {h_name} as scratched (matched '{name}')")
                    scratches_marked += 1
                    # Don't break here, in case multiple entries match? No, usually one horse per name.
                    break
        return scratches_marked
    except Exception as e:
        logger.error(f"Error marking scratches: {e}")
        return 0


def race_is_completed_and_verified(supabase, race_key: str) -> Tuple[bool, Optional[Dict], int]:
    """
    Determine whether a race already has a trustworthy set of results in the DB.
    """
    try:
        existing = supabase.table('hranalyzer_races').select('id, race_status').eq('race_key', race_key).execute()
        if not existing.data:
            return False, None, 0

        race_record = existing.data[0]
        if race_record.get('race_status') != 'completed':
            return False, race_record, 0

        has_winner = False
        finisher_count = 0
        try:
            w_check = supabase.table('hranalyzer_race_entries')\
                .select('id, finish_position')\
                .eq('race_id', race_record['id'])\
                .gt('finish_position', 0)\
                .execute()
            if w_check.data:
                has_winner = any(e['finish_position'] == 1 for e in w_check.data)
                finisher_count = len(w_check.data)
        except Exception as e:
            logger.debug(f"Error checking winner for {race_key}: {e}")

        return has_winner and finisher_count >= 3, race_record, finisher_count
    except Exception as e:
        logger.debug(f"Error checking status for {race_key}: {e}")
        return False, None, 0


def crawl_specific_races(target_date: date, race_targets: List[Tuple[str, int]]) -> Dict:
    """
    Retry a focused list of exact races, rather than sweeping all race numbers.
    """
    grouped_targets = defaultdict(set)
    for track_code, race_number in race_targets or []:
        normalized_track = str(track_code or '').strip().upper()
        if not normalized_track:
            continue
        try:
            normalized_race = int(race_number)
        except (TypeError, ValueError):
            continue
        grouped_targets[normalized_track].add(normalized_race)

    stats = {
        'date': target_date.strftime('%Y-%m-%d'),
        'tracks_checked': len(grouped_targets),
        'races_requested': sum(len(races) for races in grouped_targets.values()),
        'races_found': 0,
        'races_inserted': 0,
        'races_failed': 0,
        'races_skipped_verified': 0,
        'success': True,
    }

    if not grouped_targets:
        return stats

    logger.info(
        "Retrying %s unresolved races for %s",
        stats['races_requested'],
        target_date,
    )

    supabase = get_supabase_client()

    for track_code in grouped_targets:
        log_container_memory(f"Focused retry starting track {track_code}")
        full_card_race_map = {}
        full_card_pdf = download_full_card_pdf(track_code, target_date)
        if full_card_pdf:
            try:
                full_card_race_map = build_race_map(parse_equibase_full_card(full_card_pdf))
                del full_card_pdf
                if full_card_race_map:
                    logger.info(
                        "Loaded %s races from full-card cache for unresolved %s retries on %s",
                        len(full_card_race_map),
                        track_code,
                        target_date,
                    )
            except Exception as e:
                logger.warning(f"Could not build full-card cache for unresolved {track_code} retries: {e}")
                full_card_race_map = {}

        for race_num in sorted(grouped_targets[track_code]):
            race_key = f"{track_code}-{target_date.strftime('%Y%m%d')}-{race_num}"
            verified, _, finisher_count = race_is_completed_and_verified(supabase, race_key)
            if verified:
                logger.info(
                    "Skipping unresolved retry for %s (already verified with %s finishers)",
                    race_key,
                    finisher_count,
                )
                stats['races_skipped_verified'] += 1
                continue

            race_data = extract_race_from_pdf(
                build_equibase_url(track_code, target_date, race_num),
                max_retries=2,
                cached_full_card_races=full_card_race_map,
            )
            if not race_data or not race_data.get('horses'):
                logger.warning(f"Unresolved retry could not fetch {race_key}")
                stats['races_failed'] += 1
                continue

            stats['races_found'] += 1
            if insert_race_to_db(supabase, track_code, target_date, race_data, race_num):
                stats['races_inserted'] += 1
            else:
                stats['races_failed'] += 1

            time.sleep(1)

        full_card_race_map = {}
        gc.collect()
        log_container_memory(f"Focused retry finished track {track_code}")

    close_shared_equibase_webdriver(reason="focused retry crawl complete")
    return stats


def crawl_historical_races(target_date: date, tracks: List[str] = None) -> Dict:
    """
    Crawl historical races for a specific date

    Args:
        target_date: Date to crawl (usually yesterday)
        tracks: List of track codes to check (default: COMMON_TRACKS)

    Returns:
        Dict with crawl statistics
    """
    if tracks is None:
        tracks = COMMON_TRACKS

    logger.info(f"Starting crawl for {target_date}")
    logger.info(f"Tracks to check: {', '.join(tracks)}")

    supabase = get_supabase_client()

    stats = {
        'date': target_date.strftime('%Y-%m-%d'),
        'tracks_checked': len(tracks),
        'tracks_with_races': 0,
        'races_found': 0,
        'races_inserted': 0,
        'races_failed': 0
    }

    for track_code in tracks:
        logger.info(f"\nProcessing track: {track_code}")
        log_container_memory(f"Historical crawl starting track {track_code}")

        track_had_races = False
        race_num = 1
        missing_consecutive = 0
        full_card_race_map = {}

        full_card_pdf = download_full_card_pdf(track_code, target_date)
        if full_card_pdf:
            try:
                full_card_race_map = build_race_map(parse_equibase_full_card(full_card_pdf))
                del full_card_pdf
                if full_card_race_map:
                    logger.info(
                        "Loaded %s races from full-card cache for %s on %s",
                        len(full_card_race_map),
                        track_code,
                        target_date,
                    )
            except Exception as e:
                logger.warning(f"Could not build full-card cache for {track_code} {target_date}: {e}")
                full_card_race_map = {}

        # Try up to 12 races per track
        while race_num <= 12:
            try:
                # Check if race is already completed in DB to avoid re-downloading
                race_key = f"{track_code}-{target_date.strftime('%Y%m%d')}-{race_num}"
                verified, race_record, finisher_count = race_is_completed_and_verified(supabase, race_key)
                if verified:
                    logger.info(f"Skipping {race_key} (Already Completed & Verified with {finisher_count} finishers)")
                    race_num += 1
                    track_had_races = True
                    continue
                if race_record and race_record.get('race_status') == 'completed':
                    if finisher_count > 0:
                        logger.warning(f"Race {race_key} has winner but only {finisher_count} finisher(s). Re-crawling for full results...")
                    else:
                        logger.warning(f"Race {race_key} marked completed but has no winner. Re-crawling...")
            except Exception as e:
                logger.debug(f"Error checking status for {race_key}: {e}")

            pdf_url = build_equibase_url(track_code, target_date, race_num)

            # Extract race data
            race_data = extract_race_from_pdf(
                pdf_url,
                max_retries=2,
                cached_full_card_races=full_card_race_map,
            )

            if not race_data or not race_data.get('horses'):
                missing_consecutive += 1
                if missing_consecutive >= 3:
                    if race_num == 1:
                        logger.info(f"No race 1 found at {track_code}, moving to next track")
                    else:
                        logger.info(f"Stop searching {track_code} after {missing_consecutive} consecutive misses.")
                    break
                else:
                    logger.info(f"Race {race_num} at {track_code} not found. Skipping to check next (miss {missing_consecutive}/3)")
                    race_num += 1
                    continue
            
            # Reset missing count if we found a race
            missing_consecutive = 0

            # Mark that this track had races
            if not track_had_races:
                track_had_races = True
                stats['tracks_with_races'] += 1

            stats['races_found'] += 1

            # Insert to database
            success = insert_race_to_db(supabase, track_code, target_date, race_data, race_num)
            if success:
                stats['races_inserted'] += 1
                logger.info(f"✓ Successfully processed {track_code} Race {race_num}")
            else:
                stats['races_failed'] += 1
                logger.error(f"✗ Failed to insert {track_code} Race {race_num}")

            race_num += 1
            time.sleep(1)  # Be polite to Equibase servers

        full_card_race_map = {}
        gc.collect()
        log_container_memory(f"Historical crawl finished track {track_code}")

    close_shared_equibase_webdriver(reason="historical crawl complete")
    logger.info("\n" + "="*80)
    logger.info("Crawl Summary:")
    logger.info(f"  Date: {stats['date']}")
    logger.info(f"  Tracks checked: {stats['tracks_checked']}")
    logger.info(f"  Tracks with races: {stats['tracks_with_races']}")
    logger.info(f"  Races found: {stats['races_found']}")
    logger.info(f"  Races inserted: {stats['races_inserted']}")
    logger.info(f"  Races failed: {stats['races_failed']}")
    logger.info("="*80 + "\n")

    stats['success'] = stats['races_inserted'] > 0 or stats['races_found'] == 0
    return stats


if __name__ == "__main__":
    from datetime import timedelta

    # Default to yesterday
    target = date.today() - timedelta(days=1)

    # Or specify date via command line
    if len(sys.argv) > 1:
        try:
            target = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

    logger.info(f"Starting Equibase crawler for {target}")
    stats = crawl_historical_races(target)

    if stats['races_inserted'] > 0:
        logger.info(f"✓ Crawl completed successfully!")
        sys.exit(0)
    else:
        logger.error(f"✗ Crawl completed with no races inserted")
        sys.exit(1)
