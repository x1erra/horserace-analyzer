import os
import sys
import types
import unittest
from unittest.mock import MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

supabase_client_stub = types.ModuleType("supabase_client")
supabase_client_stub.get_supabase_client = MagicMock()
supabase_client_stub.reset_supabase_client = MagicMock()
sys.modules["supabase_client"] = supabase_client_stub

import parse_drf


class FakePdfPage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class TestParseDrf(unittest.TestCase):
    def test_extract_header_metadata_prefers_header_track_over_pp_running_lines(self):
        page_text = """Daily Racing Form Woodbine(4/18/2026)
INDEXTOENTRIES
>A> ExampleHorse,1
1
Woodbine
MdSpWt
14æ25=6SAR fm 1 Ñ 23§ :49 1:14¦1:38¦ MdSpWt79k
"""

        metadata = parse_drf.extract_header_metadata(FakePdfPage(page_text))

        self.assertEqual(metadata["track_code"], "WO")
        self.assertEqual(metadata["track_name"], "Woodbine")
        self.assertEqual(metadata["race_date"], "2026-04-18")

    def test_race_header_detection_accepts_woodbine(self):
        page_text = """2
Woodbine
Claiming
6Furlongs
Posttime:1:20ET
"""

        self.assertEqual(parse_drf.is_race_header_page(page_text), (True, 2))

    def test_extract_race_content_from_index_page_preserves_race_one_header_and_entries(self):
        page_text = """Daily Racing Form GulfstreamPark(4/10/2026)
INDEXTOENTRIES
>A> SwampFox,1 VanCleef,1
INDEXTOTRAINERS
>A> AntonacciPhilip,1
1
Gulfstream Park
Md17500(17.5-16)
1MILE (Turf).
Posttime:12:50ET Wagers:$1DailyDouble
1
SwampFox B.g.4 (Feb) Life 4 M 1 0 $8,190 63
Sire: War of Will
2
Numinous B.g.5 (Feb) Life 8 M 0 0 $4,330 63
Sire: Catholic Boy
"""

        trimmed = parse_drf.extract_race_content_from_index_page(page_text, "Gulfstream Park")

        self.assertTrue(trimmed.startswith("1\nGulfstream Park"))

        is_header, race_number = parse_drf.is_race_header_page(trimmed)
        self.assertEqual((is_header, race_number), (True, 1))

        race = parse_drf.extract_race_header_from_page(trimmed, 1)
        self.assertEqual([entry["program_number"] for entry in race["embedded_entries"]], ["1", "2"])
        self.assertEqual([entry["horse_name"] for entry in race["embedded_entries"]], ["SWAMPFOX", "NUMINOUS"])


if __name__ == "__main__":
    unittest.main()
