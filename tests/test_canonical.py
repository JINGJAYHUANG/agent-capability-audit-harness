from __future__ import annotations

import json
import unittest
from pathlib import Path

from acah.canonical import (
    canonical_dumps,
    normalize_relative_path,
    sha256_bytes,
    sha256_file,
    sha256_json,
    sha256_text,
    write_json,
)
from tests.helpers import temporary_directory


class CanonicalTests(unittest.TestCase):
    def test_canonical_order(self):
        self.assertEqual(canonical_dumps({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_canonical_unicode(self):
        self.assertIn("测试", canonical_dumps({"value": "测试"}))

    def test_canonical_rejects_nan(self):
        with self.assertRaises(ValueError):
            canonical_dumps({"value": float("nan")})

    def test_sha256_bytes(self):
        self.assertEqual(sha256_bytes(b"abc"), sha256_text("abc"))

    def test_sha256_json_ignores_mapping_order(self):
        self.assertEqual(sha256_json({"a": 1, "b": 2}), sha256_json({"b": 2, "a": 1}))

    def test_write_json_is_canonical(self):
        with temporary_directory() as temp:
            path = temp / "value.json"
            write_json(path, {"b": 1, "a": 2})
            self.assertEqual(path.read_text(), '{"a":2,"b":1}\n')

    def test_sha256_file_changes(self):
        with temporary_directory() as temp:
            path = temp / "value.txt"
            path.write_text("a")
            first = sha256_file(path)
            path.write_text("b")
            self.assertNotEqual(first, sha256_file(path))

    def test_safe_relative_path(self):
        self.assertEqual(normalize_relative_path("a/b.txt"), "a/b.txt")

    def test_backslash_normalization(self):
        self.assertEqual(normalize_relative_path("a\\b.txt"), "a/b.txt")

    def test_reject_absolute_path(self):
        with self.assertRaises(ValueError):
            normalize_relative_path("/etc/passwd")

    def test_reject_parent_segment(self):
        with self.assertRaises(ValueError):
            normalize_relative_path("a/../b")

    def test_reject_empty_path(self):
        with self.assertRaises(ValueError):
            normalize_relative_path("")
