import os
import sys
import types
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

supabase_client_stub = types.ModuleType("supabase_client")
supabase_client_stub.get_supabase_client = MagicMock()
sys.modules["supabase_client"] = supabase_client_stub

crawl_equibase_stub = types.ModuleType("crawl_equibase")
crawl_equibase_stub.get_or_create_track = MagicMock()
crawl_equibase_stub.get_or_create_participant = MagicMock()
crawl_equibase_stub.normalize_pgm = lambda value: value
crawl_equibase_stub.COMMON_TRACKS = []
sys.modules["crawl_equibase"] = crawl_equibase_stub

import crawl_entries

# Allow other test modules to import the real crawl_equibase module later.
sys.modules.pop("crawl_equibase", None)


class TestCrawlEntries(unittest.TestCase):
    def test_fetch_hrn_entries_uses_h4_name_without_sire_text(self):
        html = """
        <html>
          <body>
            <table>
              <tr>
                <th>#</th>
                <th>PP</th>
                <th>Horse</th>
                <th>Trainer / Jockey</th>
                <th>ML</th>
              </tr>
              <tr>
                <td>2</td>
                <td>2</td>
                <td data-label="Horse / Sire">
                  <h4>Gentlemens Game </h4>
                  <p>Eagle Power</p>
                </td>
                <td>
                  <p>Jorge Duarte-Noriega</p>
                  <p>Kody Kellenberger</p>
                </td>
                <td>20/1</td>
              </tr>
            </table>
          </body>
        </html>
        """
        response = types.SimpleNamespace(status_code=200, text=html)

        with patch.object(crawl_entries.requests, "get", return_value=response):
            races = crawl_entries.fetch_hrn_entries("TUP", date.fromisoformat("2026-04-02"))

        self.assertEqual(len(races), 1)
        self.assertEqual(races[0]["entries"][0]["horse_name"], "Gentlemens Game")
        self.assertEqual(races[0]["entries"][0]["morning_line_odds"], "20/1")

    def test_fetch_hrn_entries_strips_numeric_suffix_from_horse_name(self):
        html = """
        <html>
          <body>
            <table>
              <tr>
                <th>#</th>
                <th>PP</th>
                <th>Horse</th>
                <th>Trainer / Jockey</th>
                <th>ML</th>
              </tr>
              <tr>
                <td>7</td>
                <td>7</td>
                <td data-label="Horse / Sire">
                  <h4>Nyfive (97)</h4>
                </td>
                <td>
                  <p>Trainer Name</p>
                  <p>Jockey Name</p>
                </td>
                <td>4/1</td>
              </tr>
            </table>
          </body>
        </html>
        """
        response = types.SimpleNamespace(status_code=200, text=html)

        with patch.object(crawl_entries.requests, "get", return_value=response):
            races = crawl_entries.fetch_hrn_entries("GP", date.fromisoformat("2026-04-02"))

        self.assertEqual(len(races), 1)
        self.assertEqual(races[0]["entries"][0]["horse_name"], "Nyfive")


if __name__ == "__main__":
    unittest.main()
