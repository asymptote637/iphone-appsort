"""Custom policies, recency, saved profiles and synthetic demo consistency."""
from __future__ import annotations

import copy
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from appsort.__main__ import demo_state
from appsort.controller import Organizer, save_json
from appsort.core import SortError, apps, diff, rank_layout, validate_options
from appsort.usage import FocusChange, import_counts, read_usage

ROOT = Path(__file__).resolve().parents[1]


def icon(name):
    return {"bundleIdentifier": "com.example." + name, "displayName": name}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.icons = [icon(str(i)) for i in range(27)]
        self.layout = [[self.icons[-1]], self.icons[:24], self.icons[24:-1]]
        self.usage = {"days": 7, "apps": {a["bundleIdentifier"]: {"opens": i + 1, "seconds": 50 - i,
                      "last_open": f"2026-01-01T{i % 24:02}:00:00+00:00"} for i, a in enumerate(self.icons)}}

    def test_recency_uses_absolute_time_and_keeps_unobserved_last(self):
        data = {"days": 7, "apps": {
            "com.example.0": {"opens": 99, "last_open": "2026-01-01T10:00:00+08:00"},
            "com.example.1": {"opens": 1, "last_open": "2026-01-01T04:00:00Z"}}}
        result = rank_layout(self.layout, data, metric="recent")["layout"]
        self.assertEqual([a["displayName"] for a in apps(result)][1:5], ["1", "0", "2", "3"])

    def test_recency_without_times_does_not_substitute_open_counts(self):
        with self.assertRaises(SortError):
            rank_layout(self.layout, {"days": 7, "apps": {"com.example.0": {"opens": 99}}}, metric="recent")

    def test_preserved_folder_recency_uses_latest_child(self):
        folder = {"displayName": "Utilities", "iconLists": [[icon("a"), icon("b")]]}
        layout = [[], [folder, icon("c")]]
        data = {"days": 7, "apps": {
            "com.example.a": {"last_open": "2026-01-01T09:00:00Z"},
            "com.example.b": {"last_open": "2026-01-01T08:00:00Z"},
            "com.example.c": {"last_open": "2026-01-01T10:00:00Z"}}}
        result = rank_layout(layout, data, metric="recent", folders="preserve")["layout"]
        self.assertEqual(result[1][0]["displayName"], "c")
        self.assertEqual(result[1][1]["displayName"], "Utilities")

    def test_custom_capacity_preserves_inventory_dock_and_order(self):
        for capacity in (1, 2, 3, 7, 12, 24):
            with self.subTest(capacity=capacity):
                result = rank_layout(self.layout, self.usage, capacity=capacity, widget_mode="separate")["layout"]
                self.assertEqual(result[0], self.layout[0])
                self.assertTrue(all(len(p) <= capacity for p in result[1:]))
                self.assertEqual([a["displayName"] for a in apps(result)][1:], [str(i) for i in reversed(range(26))])

    def test_small_page_budget_groups_only_necessary_lowest_tail(self):
        result = rank_layout(self.layout, self.usage, capacity=7, page_limit=2, widget_mode="separate")
        self.assertEqual(len(result["layout"]) - 1, 2)
        self.assertEqual(result["tail_folder"]["apps"], [str(i) for i in reversed(range(13))])
        self.assertEqual(len(list(apps(result["layout"]))), 27)

    def test_invalid_options_are_actionable_and_not_coerced(self):
        invalid = [{"capacity": 0}, {"capacity": 25}, {"capacity": True}, {"capacity": 8.5},
                   {"capacity": "8"}, {"page_limit": 0}, {"page_limit": 16}, {"page_limit": False},
                   {"pinned": "app"}, {"pinned": [""]}, {"pinned": ["a", "a"]},
                   {"metric": "pickups"}, [], None]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(SortError):
                validate_options(value)

    def test_timestamps_require_timezone(self):
        data = copy.deepcopy(self.usage)
        data["apps"]["com.example.0"]["last_open"] = "2026-01-01T10:00:00"
        with self.assertRaises(SortError):
            rank_layout(self.layout, data, metric="recent")
        with self.assertRaises(SortError):
            import_counts("bundle_id,opens,last_open\ncom.example.a,1,2026-01-01T10:00:00", 7, "demo")

    def test_csv_recency_roundtrip_accepts_timezone(self):
        data = import_counts("bundle_id,opens,seconds,last_open\ncom.example.a,1,12,2026-01-01T10:00:00+08:00", 7, "demo")
        self.assertEqual(data["apps"]["com.example.a"]["last_open"], "2026-01-01T10:00:00+08:00")
        self.assertEqual(data["source"], "imported_csv")


class ProfileTests(unittest.TestCase):
    def test_demo_windows_keep_fictional_values_and_never_collect_records(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Organizer(Path(directory), demo=True)
            demo_state(tool)
            before = copy.deepcopy(tool.view()["usage"]["apps"])
            tool.propose({"days": 30, "metric": "recent", "capacity": 12})
            self.assertEqual(tool.view()["usage"]["apps"], before)
            self.assertEqual(tool.view()["usage"]["days"], 30)
            self.assertEqual(tool.view()["usage"]["source"], "demo")

    def test_profile_persists_and_same_name_updates_without_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Organizer(Path(directory), demo=True)
            first = {"metric": "recent", "capacity": 12, "page_limit": 5, "pinned": []}
            tool.save_profile(" Weekdays ", first)
            second = {**first, "capacity": 8}
            tool.save_profile("Weekdays", second)
            reopened = Organizer(Path(directory), demo=True)
            profiles = reopened.view()["profiles"]
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["name"], "Weekdays")
            self.assertEqual(profiles[0]["options"], second)
            self.assertFalse((Path(directory) / "current.plist").exists())

    def test_invalid_profile_never_replaces_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Organizer(Path(directory), demo=True)
            tool.save_profile("Good", {"capacity": 8})
            for name, options in [("", {}), ("x" * 61, {}), ("Good", {"capacity": 100}),
                                  ("Good", {"backend": "native"}), ("Good", [])]:
                with self.subTest(name=name, options=options), self.assertRaises(SortError):
                    tool.save_profile(name, options)
            self.assertEqual(tool.view()["profiles"][0]["options"], {"capacity": 8})


class SyncedRecencyTests(unittest.TestCase):
    def test_recency_handles_repeated_foreground_at_window_edge(self):
        now = datetime(2026, 1, 10, tzinfo=timezone.utc)
        events = [FocusChange("com.example.a", now - timedelta(days=8), True),
                  FocusChange("com.example.a", now - timedelta(days=1), True)]
        module = types.SimpleNamespace(read_segb_file=lambda _: [types.SimpleNamespace(data=bytes([i])) for i in range(len(events))])
        with tempfile.TemporaryDirectory() as directory:
            copies = Path(directory)
            folder = copies / "App.InFocus" / "synthetic-device"
            folder.mkdir(parents=True)
            (folder / "sample").touch()
            save_json(copies / "devices.json", [{"device_identifier": "synthetic-device", "platform": 2}])
            with patch.dict(sys.modules, {"ccl_segb": module}), patch("appsort.usage.decoded", side_effect=lambda b: events[b[0]]):
                result = read_usage(copies, "synthetic-device", 7, now)
            row = result["apps"]["com.example.a"]
            self.assertEqual(row["last_open"], events[-1].at.isoformat())
            self.assertEqual(row["opens"], 0)
            self.assertEqual(row["seconds"], 0)


@unittest.skipUnless(shutil.which("node"), "Node is needed only to validate the hosted demo")
class HostedDemoTests(unittest.TestCase):
    def test_demo_matches_desktop_across_policy_combinations(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Organizer(Path(directory), demo=True)
            demo_state(tool)
            view = tool.view()
            cases = []
            for metric, folders, widgets, capacity, limit in itertools.product(
                    ("opens", "seconds", "recent"), ("flatten", "preserve"), ("keep", "separate"),
                    (1, 3, 8, 12, 16, 24), (1, 2, 5, 15)):
                options = {"metric": metric, "days": 7, "folders": folders, "widget_mode": widgets,
                           "capacity": capacity, "page_limit": limit, "pinned": ["com.example.messages"]}
                try:
                    result = rank_layout(view["current"], view["usage"], **options)
                    cases.append({"options": options, "layout": result["layout"], "diff": diff(view["current"], result["layout"])})
                except SortError:
                    cases.append({"options": options, "error": True})
            script = r'''
const fs=require('fs'),assert=require('assert'),{demoPropose}=require('./scripts/demo_logic.js');
const {data,cases}=JSON.parse(fs.readFileSync(0,'utf8'));
for(const c of cases){
  let result,error=false;try{result=demoPropose(data,c.options);}catch(e){error=true;}
  assert.strictEqual(error,Boolean(c.error),JSON.stringify(c.options));
  if(!error){assert.deepStrictEqual(result.layout,c.layout);assert.deepStrictEqual(result.proposal.diff,c.diff);}
}
process.stdout.write(String(cases.length));
'''
            result = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps({"data": view, "cases": cases}),
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "288")

    def test_real_and_generated_ui_scripts_parse(self):
        subprocess.run([sys.executable, "scripts/build_demo.py"], cwd=ROOT, check=True, capture_output=True)
        script = r'''const fs=require('fs');for(const p of ['web/index.html','docs/demo/index.html'])new Function(fs.readFileSync(p,'utf8').split('<script>')[1].split('</script>')[0]);'''
        result = subprocess.run([shutil.which("node"), "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
