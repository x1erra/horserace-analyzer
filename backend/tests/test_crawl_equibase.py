import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

supabase_client_stub = types.ModuleType("supabase_client")
supabase_client_stub.get_supabase_client = MagicMock()
sys.modules.setdefault("supabase_client", supabase_client_stub)

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = MagicMock()
sys.modules.setdefault("dotenv", dotenv_stub)

cloudscraper_stub = types.ModuleType("cloudscraper")
cloudscraper_stub.create_scraper = MagicMock()
sys.modules.setdefault("cloudscraper", cloudscraper_stub)

pdfplumber_stub = types.ModuleType("pdfplumber")
pdfplumber_stub.open = MagicMock()
sys.modules.setdefault("pdfplumber", pdfplumber_stub)

curl_requests_stub = types.SimpleNamespace(get=MagicMock())
curl_cffi_stub = types.ModuleType("curl_cffi")
curl_cffi_stub.requests = curl_requests_stub
sys.modules.setdefault("curl_cffi", curl_cffi_stub)

import crawl_equibase


class TestCrawlEquibase(unittest.TestCase):
    def setUp(self):
        crawl_equibase._equibase_cookie_cache['cookies'] = None
        crawl_equibase._equibase_cookie_cache['fetched_at'] = 0.0

    def test_build_race_map_indexes_valid_races_only(self):
        race_map = crawl_equibase.build_race_map([
            {"race_number": 1, "horses": [{"horse_name": "Alpha"}]},
            {"race_number": "2", "horses": [{"horse_name": "Bravo"}]},
            {"race_number": None, "horses": [{"horse_name": "Skip"}]},
            {"race_number": 3, "horses": []},
        ])

        self.assertEqual(sorted(race_map.keys()), [1, 2])
        self.assertEqual(race_map[2]["horses"][0]["horse_name"], "Bravo")

    def test_download_pdf_tries_layered_downloaders_until_one_succeeds(self):
        with patch.object(crawl_equibase, "download_pdf_via_curl_cffi", return_value=None) as curl_dl, \
             patch.object(crawl_equibase, "download_pdf_via_cloudscraper", return_value=None) as cloud_dl, \
             patch.object(crawl_equibase, "download_pdf_via_requests", return_value=b"%PDF via requests") as req_dl, \
             patch.object(crawl_equibase, "download_pdf_via_powershell") as pwsh_dl:
            content = crawl_equibase.download_pdf("https://example.test/race.pdf", timeout=12)

        self.assertEqual(content, b"%PDF via requests")
        curl_dl.assert_called_once()
        cloud_dl.assert_called_once()
        req_dl.assert_called_once()
        pwsh_dl.assert_not_called()

    def test_page_looks_like_imperva_detects_interstitial(self):
        self.assertTrue(crawl_equibase.page_looks_like_imperva("<title>Pardon Our Interruption</title>"))
        self.assertFalse(crawl_equibase.page_looks_like_imperva("<html><body>%PDF</body></html>"))

    def test_download_pdf_uses_selenium_as_last_resort(self):
        with patch.object(crawl_equibase, "download_pdf_via_curl_cffi", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_cloudscraper", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_requests", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_powershell", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_selenium", return_value=b"%PDF via selenium") as selenium_dl:
            content = crawl_equibase.download_pdf("https://example.test/race.pdf", timeout=12)

        self.assertEqual(content, b"%PDF via selenium")
        selenium_dl.assert_called_once()

    def test_download_pdf_via_selenium_replays_browser_cookies(self):
        response = types.SimpleNamespace(
            status_code=200,
            content=b"%PDF from cookie replay",
            headers={"Content-Type": "application/pdf"},
        )

        with patch.object(crawl_equibase, "get_equibase_browser_cookies", return_value={"visid": "abc"}), \
             patch.object(crawl_equibase.requests, "get", return_value=response) as requests_get:
            content = crawl_equibase.download_pdf_via_selenium("https://example.test/race.pdf", timeout=9)

        self.assertEqual(content, b"%PDF from cookie replay")
        self.assertEqual(requests_get.call_args.kwargs["cookies"], {"visid": "abc"})

    def test_parse_equibase_static_pdf_url_extracts_metadata(self):
        parsed = crawl_equibase.parse_equibase_static_pdf_url(
            "https://www.equibase.com/static/chart/pdf/PRX033126USA7.pdf"
        )

        self.assertIsNotNone(parsed)
        track_code, race_date, race_number = parsed
        self.assertEqual(track_code, "PRX")
        self.assertEqual(race_date.isoformat(), "2026-03-31")
        self.assertEqual(race_number, 7)

    def test_extract_race_from_pdf_falls_back_to_full_card(self):
        fallback_races = [
            {"race_number": 1, "horses": [{"horse_name": "Alpha"}]},
            {"race_number": 2, "horses": [{"horse_name": "Bravo"}]},
        ]

        with patch.object(crawl_equibase, "download_pdf", return_value=None), \
             patch.object(crawl_equibase, "download_full_card_pdf", return_value=b"%PDF full card"), \
             patch.object(crawl_equibase, "parse_equibase_full_card", return_value=fallback_races):
            race = crawl_equibase.extract_race_from_pdf(
                "https://www.equibase.com/static/chart/pdf/PRX033126USA2.pdf",
                max_retries=1,
            )

        self.assertEqual(race["race_number"], 2)
        self.assertEqual(race["horses"][0]["horse_name"], "Bravo")

    def test_extract_race_from_pdf_keeps_existing_success_path(self):
        parsed_race = {"race_number": 2, "horses": [{"horse_name": "Bravo"}]}

        with patch.object(crawl_equibase, "download_pdf", return_value=b"%PDF single race"), \
             patch.object(crawl_equibase, "parse_equibase_pdf", return_value=parsed_race), \
             patch.object(crawl_equibase, "download_full_card_pdf") as full_card_download:
            race = crawl_equibase.extract_race_from_pdf(
                "https://www.equibase.com/static/chart/pdf/PRX033126USA2.pdf",
                max_retries=1,
            )

        self.assertEqual(race, parsed_race)
        full_card_download.assert_not_called()

    def test_extract_race_from_pdf_uses_cached_full_card_before_network(self):
        cached_races = {
            2: {"race_number": 2, "horses": [{"horse_name": "Bravo"}]},
        }

        with patch.object(crawl_equibase, "download_pdf") as download_pdf_mock:
            race = crawl_equibase.extract_race_from_pdf(
                "https://www.equibase.com/static/chart/pdf/PRX033126USA2.pdf",
                max_retries=1,
                cached_full_card_races=cached_races,
            )

        self.assertEqual(race["race_number"], 2)
        download_pdf_mock.assert_not_called()

    def test_extract_race_from_pdf_returns_none_when_full_card_has_no_target_race(self):
        with patch.object(crawl_equibase, "download_pdf", return_value=None), \
             patch.object(crawl_equibase, "download_full_card_pdf", return_value=b"%PDF full card"), \
             patch.object(
                 crawl_equibase,
                 "parse_equibase_full_card",
                 return_value=[{"race_number": 1, "horses": [{"horse_name": "Alpha"}]}],
             ):
            race = crawl_equibase.extract_race_from_pdf(
                "https://www.equibase.com/static/chart/pdf/PRX033126USA4.pdf",
                max_retries=1,
            )

        self.assertIsNone(race)


if __name__ == "__main__":
    unittest.main()
