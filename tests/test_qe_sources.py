import unittest

from qe_sources import (
    _add_record_evidence,
    _merge_records,
    _merge_target_fixture,
    football_data_stats,
)


class SourceMergeTests(unittest.TestCase):
    def test_official_source_wins_and_aliases_still_merge(self):
        espn = _add_record_evidence(
            {
                "home": "Liverpool",
                "away": "Nottingham Forest",
                "kickoff": "2026-08-29T11:30:00Z",
                "competition": "English Premier League",
                "status": "STATUS_SCHEDULED",
                "venue_name": "Anfield",
            },
            "ESPN",
            "B",
            "https://example.test/espn",
        )
        official = _add_record_evidence(
            {
                "home": "Liverpool",
                "away": "Nott'm Forest",
                "kickoff": "2026-08-29T11:30:00Z",
                "competition": "Premier League",
                "phase": "Regular season",
                "status": "SCHEDULED",
                "venue_name": "Anfield",
                "neutral": False,
            },
            "PremierLeague.com",
            "A",
            "https://example.test/official",
        )

        merged = _merge_records([espn, official])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["away"], "Nott'm Forest")
        self.assertEqual(merged[0]["competition"], "Premier League")
        self.assertEqual(merged[0]["status"], "SCHEDULED")
        self.assertEqual(
            {provider["source"] for provider in merged[0]["providers"]},
            {"ESPN", "PremierLeague.com"},
        )

    def test_verified_kickoff_replaces_date_only_form_identity(self):
        base = {
            "home": "Liverpool",
            "away": "Nottingham Forest",
            "kickoff": "2026-08-29",
            "league_code": "eng.1",
        }
        official = _add_record_evidence(
            {
                "home": "Liverpool",
                "away": "Nott'm Forest",
                "kickoff": "2026-08-29T11:30:00Z",
                "competition": "Premier League",
                "phase": "Regular season",
                "status": "SCHEDULED",
                "venue_name": "Anfield",
                "neutral": False,
                "league_code": "eng.1",
            },
            "PremierLeague.com",
            "A",
            "https://example.test/official",
        )

        merged = _merge_target_fixture(base, [official])

        self.assertEqual(merged["kickoff"], "2026-08-29T11:30:00Z")
        self.assertEqual(merged["venue_name"], "Anfield")

    def test_football_data_excludes_target_day_and_future_results(self):
        header = "Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,HY,AY\n"
        current = header + (
            "28/08/2026,Liverpool,Arsenal,2,0,12,8,5,2,6,3,1,2\n"
            "29/08/2026,Chelsea,Nottingham Forest,0,1,10,9,3,4,5,4,2,1\n"
            "30/08/2026,Liverpool,Chelsea,3,0,15,7,7,2,8,2,1,3\n"
        )
        previous = header + (
            "24/05/2026,Liverpool,Everton,1,1,11,9,4,3,5,4,2,2\n"
            "24/05/2026,Nottingham Forest,Burnley,2,0,13,6,5,1,7,2,1,3\n"
        )

        class FakeClient(object):
            def get_text(self, url, **_kwargs):
                return (current if "/2627/" in url else previous), None, 1

        stats, statuses = football_data_stats(
            {
                "home": "Liverpool",
                "away": "Nottingham Forest",
                "kickoff": "2026-08-29T11:30:00Z",
                "league_code": "eng.1",
            },
            FakeClient(),
        )

        current_status = next(item for item in statuses if item["source"] == "Football-Data:2627")
        self.assertEqual(current_status["records"], 1)
        used_dates = [
            row["Date"]
            for side in ("home", "away")
            for row in stats[side]["rows"]
        ]
        self.assertNotIn("29/08/2026", used_dates)
        self.assertNotIn("30/08/2026", used_dates)


if __name__ == "__main__":
    unittest.main()
