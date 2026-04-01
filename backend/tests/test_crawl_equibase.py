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
