import os
import sys
import types
import time
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
        for state in crawl_equibase._heavy_fallback_state.values():
            state['failures'] = 0
            state['cooldown_until'] = 0.0
        crawl_equibase.close_shared_equibase_webdriver()

    def test_build_race_map_indexes_valid_races_only(self):
        race_map = crawl_equibase.build_race_map([
            {"race_number": 1, "horses": [{"horse_name": "Alpha"}]},
            {"race_number": "2", "horses": [{"horse_name": "Bravo"}]},
            {"race_number": None, "horses": [{"horse_name": "Skip"}]},
            {"race_number": 3, "horses": []},
        ])

        self.assertEqual(sorted(race_map.keys()), [1, 2])
        self.assertEqual(race_map[2]["horses"][0]["horse_name"], "Bravo")

    def test_build_equibase_url_uses_tvg_host(self):
        url = crawl_equibase.build_equibase_url(
            "PRX",
            crawl_equibase.date.fromisoformat("2026-03-31"),
            7,
        )
        self.assertEqual(url, "https://tvg.equibase.com/static/chart/pdf/PRX033126USA7.pdf")

    def test_build_equibase_url_uses_canadian_suffix_for_woodbine(self):
        url = crawl_equibase.build_equibase_url(
            "WO",
            crawl_equibase.date.fromisoformat("2026-04-25"),
            1,
        )
        self.assertEqual(url, "https://tvg.equibase.com/static/chart/pdf/WO042526CAN1.pdf")

    def test_build_equibase_full_card_url_uses_tvg_host(self):
        url = crawl_equibase.build_equibase_full_card_url(
            "PRX",
            crawl_equibase.date.fromisoformat("2026-03-31"),
        )
        self.assertEqual(url, "https://tvg.equibase.com/static/chart/pdf/PRX033126USA.pdf")

    def test_build_equibase_full_card_url_uses_canadian_suffix_for_woodbine(self):
        url = crawl_equibase.build_equibase_full_card_url(
            "WO",
            crawl_equibase.date.fromisoformat("2026-04-25"),
        )
        self.assertEqual(url, "https://tvg.equibase.com/static/chart/pdf/WO042526CAN.pdf")

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

    def test_download_pdf_skips_heavy_fallbacks_when_circuit_breaker_is_open(self):
        with patch.object(crawl_equibase, "download_pdf_via_curl_cffi", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_cloudscraper", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_requests", return_value=None), \
             patch.object(crawl_equibase, "heavy_fallback_available", return_value=False), \
             patch.object(crawl_equibase, "get_shared_equibase_webdriver") as shared_driver, \
             patch.object(crawl_equibase.shutil, "which", return_value="/usr/bin/pwsh"):
            content = crawl_equibase.download_pdf("https://example.test/race.pdf", timeout=12)

        self.assertIsNone(content)
        shared_driver.assert_not_called()

    def test_download_pdf_via_cookie_replay_uses_browser_cookies(self):
        response = types.SimpleNamespace(
            status_code=200,
            content=b"%PDF from cookie replay",
            headers={"Content-Type": "application/pdf"},
        )

        with patch.object(crawl_equibase.requests, "get", return_value=response) as requests_get:
            content = crawl_equibase.download_pdf_via_cookie_replay(
                "https://example.test/race.pdf",
                {"visid": "abc"},
                timeout=9,
            )

        self.assertEqual(content, b"%PDF from cookie replay")
        self.assertEqual(requests_get.call_args.kwargs["cookies"], {"visid": "abc"})

    def test_download_pdf_via_selenium_prefers_browser_context(self):
        fake_driver = MagicMock()
        fake_driver.get_cookies.return_value = []

        with patch.object(crawl_equibase, "get_shared_equibase_webdriver", return_value=fake_driver), \
             patch.object(crawl_equibase, "warm_equibase_browser_session", return_value=True) as warm_session, \
             patch.object(crawl_equibase, "fetch_pdf_via_browser_context", return_value=b"%PDF via browser") as browser_fetch, \
             patch.object(crawl_equibase, "wait_for_downloaded_pdf") as wait_download, \
             patch.object(crawl_equibase, "download_pdf_via_cookie_replay") as cookie_replay:
            crawl_equibase._equibase_browser_session['download_dir'] = '/tmp'
            content = crawl_equibase.download_pdf_via_selenium("https://example.test/race.pdf", timeout=9)

        self.assertEqual(content, b"%PDF via browser")
        warm_session.assert_called_once()
        browser_fetch.assert_called_once()
        wait_download.assert_not_called()
        cookie_replay.assert_not_called()
        fake_driver.quit.assert_not_called()

    def test_download_pdf_via_selenium_falls_back_to_cookie_replay(self):
        fake_driver = MagicMock()
        fake_driver.get_cookies.return_value = [{"name": "visid", "value": "abc"}]

        with patch.object(crawl_equibase, "get_shared_equibase_webdriver", return_value=fake_driver), \
             patch.object(crawl_equibase, "warm_equibase_browser_session", return_value=True), \
             patch.object(crawl_equibase, "fetch_pdf_via_browser_context", return_value=None), \
             patch.object(crawl_equibase, "wait_for_downloaded_pdf", return_value=None), \
             patch.object(
                 crawl_equibase,
                 "download_pdf_via_cookie_replay",
                 return_value=b"%PDF via replay",
             ) as cookie_replay:
            crawl_equibase._equibase_browser_session['download_dir'] = '/tmp'
            content = crawl_equibase.download_pdf_via_selenium("https://example.test/race.pdf", timeout=9)

        self.assertEqual(content, b"%PDF via replay")
        self.assertEqual(cookie_replay.call_args.args[1], {"visid": "abc"})
        fake_driver.quit.assert_not_called()

    def test_download_pdf_via_selenium_skips_when_no_container_headroom(self):
        with patch.object(crawl_equibase, "get_shared_equibase_webdriver", return_value=None), \
             patch.object(crawl_equibase, "download_pdf_via_cookie_replay") as cookie_replay:
            content = crawl_equibase.download_pdf_via_selenium("https://example.test/race.pdf", timeout=9)

        self.assertIsNone(content)
        cookie_replay.assert_not_called()

    def test_parse_equibase_static_pdf_url_extracts_metadata(self):
        parsed = crawl_equibase.parse_equibase_static_pdf_url(
            "https://www.equibase.com/static/chart/pdf/PRX033126USA7.pdf"
        )

        self.assertIsNotNone(parsed)
        track_code, race_date, race_number = parsed
        self.assertEqual(track_code, "PRX")
        self.assertEqual(race_date.isoformat(), "2026-03-31")
        self.assertEqual(race_number, 7)

    def test_parse_equibase_static_pdf_url_accepts_canadian_metadata(self):
        parsed = crawl_equibase.parse_equibase_static_pdf_url(
            "https://www.equibase.com/static/chart/pdf/WO042526CAN1.pdf"
        )

        self.assertIsNotNone(parsed)
        track_code, race_date, race_number = parsed
        self.assertEqual(track_code, "WO")
        self.assertEqual(race_date.isoformat(), "2026-04-25")
        self.assertEqual(race_number, 1)

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

    def test_crawl_specific_races_only_processes_requested_targets(self):
        supabase = MagicMock()
        race_lookup = MagicMock()
        race_lookup.eq.return_value.execute.return_value.data = []
        supabase.table.return_value.select.return_value = race_lookup

        with patch.object(crawl_equibase, "get_supabase_client", return_value=supabase), \
             patch.object(crawl_equibase, "download_full_card_pdf", return_value=None), \
             patch.object(
                 crawl_equibase,
                 "extract_race_from_pdf",
                 side_effect=[
                     {"race_number": 8, "horses": [{"horse_name": "Alpha"}]},
                     {"race_number": 3, "horses": [{"horse_name": "Bravo"}]},
                 ],
             ) as extract_race, \
             patch.object(crawl_equibase, "insert_race_to_db", return_value=True) as insert_race, \
             patch.object(crawl_equibase, "close_shared_equibase_webdriver") as close_browser, \
             patch.object(crawl_equibase, "time") as time_mod:
            stats = crawl_equibase.crawl_specific_races(
                crawl_equibase.date.fromisoformat("2026-04-02"),
                [("SA", 8), ("MVR", 3)],
            )

        self.assertEqual(stats["races_requested"], 2)
        self.assertEqual(stats["races_inserted"], 2)
        self.assertEqual(extract_race.call_count, 2)
        insert_calls = [call.args[3]["race_number"] for call in insert_race.call_args_list]
        self.assertEqual(insert_calls, [8, 3])
        self.assertEqual(time_mod.sleep.call_count, 2)
        close_browser.assert_called_once()

    def test_crawl_specific_races_skips_verified_races(self):
        supabase = MagicMock()

        race_query = MagicMock()
        entries_query = MagicMock()

        def table_side_effect(name):
            table_mock = MagicMock()
            if name == "hranalyzer_races":
                table_mock.select.return_value = race_query
            elif name == "hranalyzer_race_entries":
                table_mock.select.return_value = entries_query
            else:
                table_mock.select.return_value = MagicMock()
            return table_mock

        supabase.table.side_effect = table_side_effect
        race_query.eq.return_value.execute.return_value.data = [{"id": "race-1", "race_status": "completed"}]
        entries_query.eq.return_value.gt.return_value.execute.return_value.data = [
            {"id": "e1", "finish_position": 1},
            {"id": "e2", "finish_position": 2},
            {"id": "e3", "finish_position": 3},
        ]

        with patch.object(crawl_equibase, "get_supabase_client", return_value=supabase), \
             patch.object(crawl_equibase, "download_full_card_pdf", return_value=None), \
             patch.object(crawl_equibase, "extract_race_from_pdf") as extract_race:
            stats = crawl_equibase.crawl_specific_races(
                crawl_equibase.date.fromisoformat("2026-04-02"),
                [("SA", 8)],
            )

        self.assertEqual(stats["races_requested"], 1)
        self.assertEqual(stats["races_skipped_verified"], 1)
        extract_race.assert_not_called()


if __name__ == "__main__":
    unittest.main()
