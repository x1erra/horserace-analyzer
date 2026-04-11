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


class TestParseDrf(unittest.TestCase):
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
