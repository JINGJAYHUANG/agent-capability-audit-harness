from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from acah.events import DeterministicClock, EventLog, load_events, verify_event_log
from tests.helpers import temporary_directory


class EventTests(unittest.TestCase):
    def _create_log(self, path: Path):
        log = EventLog(path, "run-123", DeterministicClock(datetime(2026, 1, 1, tzinfo=timezone.utc)))
        log.append("start", case_id=None, source="test", payload={"a": 1})
        log.append("decision", case_id="case-a", source="test", payload={"b": 2})
        log.append("end", case_id=None, source="test", payload={"c": 3})
        return log

    def test_valid_event_log(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            result = verify_event_log(path, expected_run_id="run-123")
            self.assertTrue(result.passed)
            self.assertEqual(result.details["event_count"], 3)

    def test_sequence_starts_at_zero(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            self.assertEqual(load_events(path)[0]["seq"], 0)

    def test_timestamp_increments(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            events = load_events(path)
            self.assertLess(events[0]["ts"], events[1]["ts"])

    def test_tamper_detected(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            events = load_events(path)
            events[1]["payload"]["b"] = 99
            path.write_text("\n".join(json.dumps(x, sort_keys=True) for x in events) + "\n")
            self.assertFalse(verify_event_log(path).passed)

    def test_reorder_detected(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            events = load_events(path)
            events[1], events[2] = events[2], events[1]
            path.write_text("\n".join(json.dumps(x, sort_keys=True) for x in events) + "\n")
            result = verify_event_log(path)
            self.assertFalse(result.passed)
            self.assertTrue(any("sequence" in item or "previous_hash" in item for item in result.errors))

    def test_delete_detected_by_chain(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            events = load_events(path)
            path.write_text("\n".join(json.dumps(x, sort_keys=True) for x in (events[0], events[2])) + "\n")
            self.assertFalse(verify_event_log(path).passed)

    def test_expected_run_id(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            self._create_log(path)
            result = verify_event_log(path, expected_run_id="wrong")
            self.assertFalse(result.passed)
            self.assertTrue(any("run_id" in item for item in result.errors))

    def test_invalid_json(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            path.write_text("not-json\n")
            result = verify_event_log(path)
            self.assertFalse(result.passed)

    def test_non_object_event(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            path.write_text("[]\n")
            with self.assertRaises(ValueError):
                load_events(path)

    def test_empty_event_log(self):
        with temporary_directory() as temp:
            path = temp / "events.jsonl"
            path.write_text("")
            result = verify_event_log(path)
            self.assertTrue(result.passed)
            self.assertEqual(result.details["final_event_hash"], "0" * 64)

    def test_clock_requires_timezone(self):
        with self.assertRaises(ValueError):
            DeterministicClock(datetime(2026, 1, 1))
