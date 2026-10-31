import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_forecast import forecast

DEADLINE = "2026-10-31T23:59:00+01:00"


class ForecastTests(unittest.TestCase):
    def sample(self, at, age, block="0x2"):
        return {"observed_at": at, "head_age_seconds": age, "block": block,
                "fully_synced": False}

    def test_copy_percentage_does_not_produce_sync_eta(self):
        status = self.sample("2026-10-31T12:00:00+00:00", None, "0x0")
        status["storage_migration"] = {"phase": "copying"}
        result = forecast(status, [], DEADLINE)
        self.assertEqual(result["state"], "storage_preparation")
        self.assertIsNone(result["eta_seconds"])

    def test_timestamp_catchup_includes_elapsed_network_time(self):
        first = self.sample("2026-10-31T11:50:00+00:00", 3600, "0x1")
        current = self.sample("2026-10-31T12:00:00+00:00", 2400)
        result = forecast(current, [first], DEADLINE)
        self.assertEqual(result["eta_seconds"], 1050)
        self.assertTrue(result["on_track_estimate"])

    def test_transfer_eta_is_kept_separate_from_chain_eta(self):
        first = self.sample("2026-10-31T11:56:00+00:00", None, "0x0")
        first["storage_migration"] = {"phase": "copying", "copied_bytes": 100, "total_bytes": 1000}
        current = self.sample("2026-10-31T12:00:00+00:00", None, "0x0")
        current["storage_migration"] = {"phase": "copying", "copied_bytes": 400, "total_bytes": 1000}
        result = forecast(current, [first], DEADLINE)
        self.assertEqual(result["copy_eta_seconds"], 480)
        self.assertIsNone(result["eta_seconds"])

    def test_clock_aging_with_progress_can_mean_no_catchup(self):
        first = self.sample("2026-10-31T11:50:00+00:00", 3600, "0x1")
        current = self.sample("2026-10-31T12:00:00+00:00", 3800)
        result = forecast(current, [first], DEADLINE)
        self.assertEqual(result["state"], "no_catchup_observed")
        self.assertIsNone(result["eta_seconds"])

    def test_requires_new_validated_head(self):
        first = self.sample("2026-10-31T11:50:00+00:00", 3600)
        current = self.sample("2026-10-31T12:00:00+00:00", 4200)
        self.assertEqual(forecast(current, [first], DEADLINE)["state"],
                         "waiting_for_validated_progress")

    def test_excludes_measurements_before_storage_activation(self):
        first = self.sample("2026-10-31T11:50:00+00:00", 3600, "0x1")
        current = self.sample("2026-10-31T12:00:00+00:00", 2400)
        current["storage_migration"] = {"phase": "activated", "observed_at": "2026-10-31T11:55:00+00:00"}
        self.assertIsNone(forecast(current, [first], DEADLINE)["eta_seconds"])

    def test_fresh_head_still_needs_final_rpc_confirmation(self):
        current = self.sample("2026-10-31T12:00:00+00:00", 10)
        self.assertEqual(forecast(current, [], DEADLINE)["state"],
                         "near_head_waiting_confirmation")
        current["fully_synced"] = True
        self.assertEqual(forecast(current, [], DEADLINE)["state"], "verified_synced")


if __name__ == "__main__":
    unittest.main()
