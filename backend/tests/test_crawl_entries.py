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
    def test_parse_drf_racing_dates_and_track_lookup(self):
        html = """
        <html>
          <body>
            <table>
              <tr>
                <td>MAHONING VALLEY RACE COURSE</td>
                <td>MVR</td>
                <td>
                  <ul>
                    <li>01/02/2026 - 04/10/2026 (TB)</li>
                  </ul>
                </td>
              </tr>
              <tr>
                <td>WOODBINE</td>
                <td>WO</td>
                <td>
                  <ul>
                    <li>04/18/2026 - 12/13/2026 (TB)</li>
                  </ul>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """

        schedule = crawl_entries.parse_drf_racing_dates(html)

        self.assertTrue(crawl_entries.track_has_card_via_drf("MVR", date.fromisoformat("2026-04-03"), schedule))
        self.assertFalse(crawl_entries.track_has_card_via_drf("WO", date.fromisoformat("2026-04-03"), schedule))
        self.assertIsNone(crawl_entries.track_has_card_via_drf("PRX", date.fromisoformat("2026-04-03"), schedule))

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

    def test_fetch_entry_card_prefers_tvg_before_legacy_equibase(self):
        parsed_races = [{"race_number": 1, "entries": [{"horse_name": "Test Horse"}]}]

        with patch.object(crawl_entries, "fetch_hrn_entries", return_value=[]), \
             patch.object(
                 crawl_entries,
                 "fetch_static_page",
                 side_effect=[
                     {"status": "success", "content": "<html>ok</html>", "size": 6000},
                 ],
             ) as fetch_static_mock, \
             patch.object(crawl_entries, "parse_entries_html", return_value=parsed_races):
            result = crawl_entries.fetch_entry_card("MVR", date.fromisoformat("2026-04-03"))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "equibase_tvg_entries")
        self.assertEqual(result["races"][0]["source"], "equibase_tvg_entries")
        first_url = fetch_static_mock.call_args_list[0].args[0]
        self.assertIn("tvg.equibase.com", first_url)

    def test_crawl_entries_skips_track_when_drf_schedule_confirms_no_card(self):
        supabase = MagicMock()

        with patch.object(crawl_entries, "get_supabase_client", return_value=supabase), \
             patch.object(
                 crawl_entries,
                 "fetch_drf_racing_dates",
                 return_value={"WO": [(date.fromisoformat("2026-04-18"), date.fromisoformat("2026-12-13"))]},
             ), \
             patch.object(crawl_entries, "fetch_entry_card") as fetch_entry_card_mock:
            stats = crawl_entries.crawl_entries(
                target_date=date.fromisoformat("2026-04-03"),
                tracks=["WO"],
            )

        fetch_entry_card_mock.assert_not_called()
        self.assertEqual(stats["tracks_skipped_no_card"], 1)
        self.assertEqual(stats["races_found"], 0)


if __name__ == "__main__":
    unittest.main()
