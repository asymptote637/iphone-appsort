from __future__ import annotations

import copy
import json
import plistlib
import struct
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from appsort.controller import Organizer, load_json, save_json, save_plist
from appsort.__main__ import demo_state
from appsort.core import SortError, apps, canonical, fingerprint, rank_layout, test_swap, to_cfgutil, validate
from appsort.server import make_server
from appsort.usage import APPLE_EPOCH, FocusChange, aggregate, decoded, import_counts, varint


def app(name: str) -> dict:
    return {"bundleIdentifier": "com.test." + name, "displayIdentifier": "com.test." + name, "displayName": name}


def widget() -> dict:
    return {"iconType": "custom", "displayIdentifier": "widget-1", "gridSize": "medium", "iconLists": [],
            "elements": [{"widgetIdentifier": "calendar", "uniqueIdentifier": "widget-element-1"}]}


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.layout = [[app("dock")], [app("a"), app("b"), app("c")]]
        self.usage = {"days": 7, "source": "biome_foreground", "apps": {
            "com.test.a": {"opens": 2, "seconds": 900}, "com.test.b": {"opens": 9, "seconds": 80},
            "com.test.c": {"opens": 5, "seconds": 300}}}

    def ids(self, layout):
        return [item["bundleIdentifier"] for item in apps(layout)]

    def test_count_is_primary_not_duration(self):
        result = rank_layout(self.layout, self.usage)["layout"]
        self.assertEqual(self.ids(result), ["com.test.dock", "com.test.b", "com.test.c", "com.test.a"])
        self.assertEqual(result[0], self.layout[0])

    def test_duration_is_explicit_separate_mode(self):
        result = rank_layout(self.layout, self.usage, metric="seconds")["layout"]
        self.assertEqual(self.ids(result), ["com.test.dock", "com.test.a", "com.test.c", "com.test.b"])

    def test_input_unchanged(self):
        before = copy.deepcopy(self.layout)
        rank_layout(self.layout, self.usage)
        self.assertEqual(self.layout, before)

    def test_equal_scores_stable_and_unobserved_last(self):
        data = {"days": 7, "apps": {"com.test.a": {"opens": 1}, "com.test.b": {"opens": 1}}}
        self.assertEqual(self.ids(rank_layout(self.layout, data)["layout"])[1:], ["com.test.a", "com.test.b", "com.test.c"])

    def test_pinned_first(self):
        result = rank_layout(self.layout, self.usage, pinned=["com.test.a"])["layout"]
        self.assertEqual(self.ids(result)[1], "com.test.a")

    def test_no_matching_usage_refused(self):
        with self.assertRaises(SortError):
            rank_layout(self.layout, {"days": 7, "apps": {"com.other.app": {"opens": 40}}})

    def test_period_mismatch_refused(self):
        with self.assertRaises(SortError):
            rank_layout(self.layout, self.usage, days=30)

    def test_duplicate_apps_refused(self):
        with self.assertRaises(SortError):
            validate([[], [app("a"), app("a")]])

    def test_unknown_icons_refused(self):
        with self.assertRaises(SortError):
            validate([[], [{"iconType": "unknown"}]])

    def test_flatten_folders_and_preserve_inventory(self):
        layout = [[], [{"displayName": "Folder", "iconLists": [[app("a"), app("b")]]}, app("c")]]
        result = rank_layout(layout, self.usage)["layout"]
        self.assertEqual(self.ids(result), ["com.test.b", "com.test.c", "com.test.a"])

    def test_preserve_folder_and_sort_inside(self):
        layout = [[], [{"displayName": "Folder", "iconLists": [[app("a"), app("b")]]}, app("c")]]
        result = rank_layout(layout, self.usage, folders="preserve")["layout"]
        self.assertEqual(result[1][0]["displayName"], "Folder")
        self.assertEqual(self.ids(result[1][0]["iconLists"]), ["com.test.b", "com.test.a"])

    def test_widget_bytes_and_position_preserved(self):
        layout = [[app("dock")], [widget(), app("a"), app("b"), app("c")]]
        result = rank_layout(layout, self.usage)["layout"]
        self.assertEqual(plistlib.dumps(result[1][0]), plistlib.dumps(layout[1][0]))
        self.assertEqual(self.ids(result)[1], "com.test.b")
        with self.assertRaises(SortError):
            to_cfgutil(result)

    def test_widget_capacity_accounts_for_area(self):
        icons = [app(str(index)) for index in range(20)]
        layout = [[], [widget(), *icons[:16]], icons[16:]]
        usage = {"days": 7, "apps": {a["bundleIdentifier"]: {"opens": index + 1} for index, a in enumerate(icons)}}
        result = rank_layout(layout, usage)["layout"]
        self.assertEqual(len(result[1]), 17)
        self.assertEqual(result[1][0], widget())
        self.assertEqual(len(list(apps(result))), 20)

    def test_cfgutil_folder_conversion(self):
        layout = [[app("dock")], [{"displayName": "F", "iconLists": [[app("a"), app("b")]]}]]
        self.assertEqual(to_cfgutil(layout), [["com.test.dock"], [["F", "com.test.a", "com.test.b"]]])

    def test_two_rows_max_eight_apps_and_preserve_widgets(self):
        icons = [app(str(index)) for index in range(31)]
        layout = [[], [widget(), *icons[:16]], icons[16:]]
        usage = {"days": 7, "apps": {a["bundleIdentifier"]: {"opens": index + 1} for index, a in enumerate(icons)}}
        result = rank_layout(layout, usage, capacity=8)["layout"]
        self.assertEqual(result[1][0], widget())
        self.assertEqual([sum(not bool(a.get('elements')) for a in p) for p in result[1:]], [8,8,8,7])
        self.assertEqual(self.ids(result), ['com.test.'+str(i) for i in reversed(range(31))])

    def test_separate_widget_page_and_all_app_pages_two_rows(self):
        icons = [app(str(index)) for index in range(31)]
        layout = [[], [widget(), *icons[:16]], icons[16:]]
        usage = {"days": 7, "apps": {a["bundleIdentifier"]: {"opens": index+1} for index,a in enumerate(icons)}}
        result = rank_layout(layout,usage,capacity=8,widget_mode='separate')['layout']
        self.assertEqual(result[1],[widget()])
        self.assertEqual([len(p) for p in result[2:]],[8,8,8,7])
        self.assertEqual(len(list(apps(result))),31)

    def test_page_limit_groups_only_tail_and_preserves_all_apps(self):
        icons=[app(str(i)) for i in range(113)]
        layout=[[],[widget(),*icons[:16]],*[icons[i:i+24] for i in range(16,113,24)]]
        usage={'days':7,'apps':{a['bundleIdentifier']:{'opens':i+1} for i,a in enumerate(icons)}}
        proposal=rank_layout(layout,usage,capacity=8,widget_mode='separate')
        result=proposal['layout']
        self.assertEqual(len(result)-1,15)
        self.assertEqual([len(page) for page in result[2:]],[8]*14)
        self.assertEqual(result[-1][-1]['displayName'],'末尾 App')
        self.assertEqual(proposal['tail_folder']['apps'],['1','0'])
        self.assertEqual(len(list(apps(result))),113)

    def test_swap_leaves_widget_and_dock(self):
        layout = [[app("dock")], [widget(), app("a"), app("b")]]
        trial, names = test_swap(layout)
        self.assertEqual(names, ["b", "a"])
        self.assertEqual(trial[1][0], layout[1][0])
        self.assertEqual(trial[0], layout[0])


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def event(self, seconds: int, bundle: str, front: bool = True) -> FocusChange:
        return FocusChange(bundle, self.start + timedelta(seconds=seconds), front)

    def test_deduplicates_sync_and_repeated_front_events(self):
        events = [self.event(0, "a"), self.event(0, "a"), self.event(2, "a"), self.event(10, "a", False),
                  self.event(20, "a"), self.event(30, "a", False)]
        data = aggregate(events, self.start, self.start + timedelta(seconds=50))
        self.assertEqual(data["a"], {"opens": 2, "seconds": 20})

    def test_switch_and_orphan_exit(self):
        events = [self.event(0, "a"), self.event(7, "b"), self.event(10, "a", False), self.event(17, "b", False)]
        data = aggregate(events, self.start, self.start + timedelta(seconds=50))
        self.assertEqual(data["a"], {"opens": 1, "seconds": 7})
        self.assertEqual(data["b"], {"opens": 1, "seconds": 10})

    def test_window_boundary_counts_and_duration(self):
        data = aggregate([self.event(-100, "a"), self.event(10, "a", False), self.event(200, "b")], self.start,
                         self.start + timedelta(seconds=100))
        self.assertEqual(data["a"], {"opens": 0, "seconds": 10})
        self.assertNotIn("b", data)

    def test_open_final_session_does_not_invent_unsynced_hours(self):
        data = aggregate([self.event(0, "a")], self.start, self.start + timedelta(days=1))
        self.assertEqual(data["a"], {"opens": 1, "seconds": 0})

    def test_valid_protobuf_decodes(self):
        seconds = (self.start - APPLE_EPOCH).total_seconds()
        data = b'\x18\x01\x21' + struct.pack('<d', seconds) + b'\x32\x03abc'
        self.assertEqual(decoded(data), FocusChange("abc", self.start, True))

    def test_malformed_protobuf_never_hangs_or_creates_app(self):
        for data in (b'\x80' * 100, b'\x32\xff\x7fabc', b'\x21a', b'\x00', b''):
            self.assertIsNone(decoded(data))
        with self.assertRaises(ValueError):
            varint(b'\x80' * 100, 0)

    def test_missing_foreground_flag_is_not_assumed_false(self):
        data = b'\x21' + struct.pack('<d', 1) + b'\x32\x01a'
        self.assertIsNone(decoded(data))

    def test_import_explicit_source(self):
        result = import_counts('bundle_id,opens,seconds\ncom.test.a,10,500\n', 7, "phone")
        self.assertEqual(result["source"], "imported_csv")
        self.assertEqual(result["apps"]["com.test.a"]["opens"], 10)

    def test_import_invalid_numbers_and_duplicates_refused(self):
        for body in ('a,-1,1', 'a,2,nan', 'a,1,1\na,2,3'):
            with self.assertRaises(SortError):
                import_counts('bundle_id,opens,seconds\n' + body, 7, "phone")


class FakePhone:
    def __init__(self, mode="success"):
        self.layout = [[app("dock")], [widget(), app("a"), app("b")]]
        self.device = {"udid": "phone", "version": "27.0", "name": "Test", "ecid": "0x123"}
        self.mode = mode
        self.writes = 0

    def inventory(self):
        return [dict(self.device, trusted=True)]

    def read(self, udid, icons=None):
        return copy.deepcopy(self.layout), copy.deepcopy(self.device)

    def write(self, device, layout, state, backend):
        self.writes += 1
        if self.mode == "success":
            self.layout = copy.deepcopy(layout)
        elif self.mode == "partial":
            self.layout = copy.deepcopy(layout)
            self.layout[1].append(app("extra"))
        elif self.mode == "disconnect":
            def unavailable(*_):
                raise SortError("disconnected")
            self.read = unavailable
        return {"sent": True}


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.phone = FakePhone()
        self.tool = Organizer(Path(self.temp.name), self.phone)
        self.tool.read_phone("phone")
        data = {"source": "biome_foreground", "days": 7, "phone_udid": "phone", "apps": {
            "com.test.a": {"opens": 2}, "com.test.b": {"opens": 9}}}
        save_json(self.tool.state / "usage.json", data)

    def tearDown(self):
        self.temp.cleanup()

    def test_success_test_restores_and_marks_exact_version(self):
        original = copy.deepcopy(self.phone.layout)
        result = self.tool.test("native", fingerprint(original))
        self.assertTrue(result["supported"])
        self.assertEqual(self.phone.layout, original)
        self.assertEqual(self.phone.writes, 2)
        self.assertTrue(self.tool.capable("native"))

    def test_ignored_interface_not_marked_supported(self):
        self.phone.mode = "ignored"
        result = self.tool.test("native", fingerprint(self.phone.layout))
        self.assertEqual(result["status"], "ignored")
        self.assertFalse(result["supported"])
        self.assertFalse(self.tool.capable("native"))

    def test_unconfirmed_readback_never_success(self):
        self.phone.mode = "disconnect"
        result = self.tool.test("native", fingerprint(self.phone.layout))
        self.assertEqual(result["status"], "unverified")
        self.assertFalse(result["supported"])

    def test_before_apply_requires_capability(self):
        self.tool.propose({})
        with self.assertRaises(SortError):
            self.tool.apply("native", self.tool.view()["proposal"]["proposal_hash"])
        self.assertEqual(self.phone.writes, 0)

    def test_apply_checks_readback_and_preserves_widget(self):
        self.tool.test("native", fingerprint(self.phone.layout))
        self.tool.propose({})
        result = self.tool.apply("native", self.tool.view()["proposal"]["proposal_hash"])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(self.phone.layout[1][0], widget())
        self.assertEqual(self.phone.layout[1][1]["displayName"], "b")
        self.assertTrue((self.tool.state / "backups" / (result["backup"] + ".plist")).exists())

    def test_stale_layout_prevents_any_new_write(self):
        self.tool.test("native", fingerprint(self.phone.layout))
        self.tool.propose({})
        self.phone.layout[1][1:3] = list(reversed(self.phone.layout[1][1:3]))
        before = self.phone.writes
        with self.assertRaises(SortError):
            self.tool.apply("native", self.tool.view()["proposal"]["proposal_hash"])
        self.assertEqual(self.phone.writes, before)

    def test_modified_proposal_prevents_any_write(self):
        self.tool.test("native", fingerprint(self.phone.layout))
        self.tool.propose({})
        expected = self.tool.view()["proposal"]["proposal_hash"]
        save_plist(self.tool.state / "proposal.plist", self.phone.layout)
        with self.assertRaises(SortError):
            self.tool.apply("native", expected)

    def test_system_upgrade_requires_new_test(self):
        self.tool.test("native", fingerprint(self.phone.layout))
        self.tool.propose({})
        self.phone.device["version"] = "27.1"
        before = self.phone.writes
        with self.assertRaises(SortError):
            self.tool.apply("native", self.tool.view()["proposal"]["proposal_hash"])
        self.assertEqual(self.phone.writes, before)

    def test_wrong_phone_usage_refused(self):
        save_json(self.tool.state / "usage.json", {"phone_udid": "different"})
        with self.assertRaises(SortError):
            self.tool.propose({})

    def test_restore_other_phone_and_path_traversal_refused(self):
        name = self.tool.snapshot(self.phone.layout, {"udid": "different"}, "other")
        with self.assertRaises(SortError):
            self.tool.restore(name + ".plist", "native")
        with self.assertRaises(SortError):
            self.tool.restore("../current.plist", "native")

    def test_demo_no_writes(self):
        tool = Organizer(self.tool.state, self.phone, demo=True)
        with self.assertRaises(SortError):
            tool.test("native", fingerprint(self.phone.layout))
        self.assertEqual(self.phone.writes, 0)

    def test_demo_refuses_to_overwrite_real_state(self):
        before=self.tool.current()
        with self.assertRaises(SortError):
            demo_state(Organizer(self.tool.state,self.phone,demo=True))
        self.assertEqual(self.tool.current(),before)

    def test_demo_bootstraps_preview_without_phone_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            tool=Organizer(Path(directory),demo=True)
            demo_state(tool)
            self.assertEqual(tool.view()['device']['udid'],'demo')
            self.assertEqual(tool.view()['proposal']['capacity'],8)

    def test_demo_cannot_collect_private_usage(self):
        tool = Organizer(self.tool.state, self.phone, demo=True)
        with self.assertRaises(SortError):
            tool.copy_usage()
        with self.assertRaises(SortError):
            tool.collect("any-device", 7)
        self.assertEqual(self.phone.writes, 0)

    def test_partial_test_attempts_restore_but_never_marks_capable(self):
        self.phone.mode = "partial"
        result = self.tool.test("native", fingerprint(self.phone.layout))
        self.assertEqual(result["status"], "partial")
        self.assertIn("restore", result)
        self.assertFalse(self.tool.capable("native"))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.tool = Organizer(Path(self.temp.name), FakePhone())
        self.tool.read_phone("phone")
        self.server = make_server(self.tool, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        text = urlopen(self.url).read().decode()
        self.token = text.split("const TOKEN='")[1].split("';")[0]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def test_api_requires_secret(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/api/state")
        self.assertEqual(error.exception.code, 403)

    def test_same_origin_api_works(self):
        req = Request(self.url + "/api/state", headers={"X-AppSort-Token": self.token})
        self.assertEqual(json.loads(urlopen(req).read())["device"]["udid"], "phone")

    def test_cross_origin_rejected_even_with_token(self):
        req = Request(self.url + "/api/state", headers={"X-AppSort-Token": self.token, "Origin": "https://example.com"})
        with self.assertRaises(HTTPError) as error:
            urlopen(req)
        self.assertEqual(error.exception.code, 403)

    def test_browser_write_requires_operation_confirmation(self):
        body = json.dumps({"backend": "native"}).encode()
        req = Request(self.url + "/api/test", data=body, headers={"X-AppSort-Token": self.token, "Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as error:
            urlopen(req)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.tool.adapter.writes, 0)

    def test_profile_endpoint_saves_custom_policy_without_phone_write(self):
        options = {"metric": "recent", "capacity": 5, "page_limit": 3, "pinned": []}
        body = json.dumps({"name": "Travel", "options": options}).encode()
        req = Request(self.url + "/api/profile", data=body,
                      headers={"X-AppSort-Token": self.token, "Content-Type": "application/json"})
        self.assertEqual(urlopen(req).status, 200)
        self.assertEqual(self.tool.view()["profiles"][0]["options"], options)
        self.assertEqual(self.tool.adapter.writes, 0)

    def test_propose_endpoint_honors_custom_capacity_and_page_budget(self):
        self.tool.import_usage("bundle_id,opens\ncom.test.a,3\ncom.test.b,10", 7)
        body = json.dumps({"capacity": 1, "page_limit": 2, "widget_mode": "separate"}).encode()
        req = Request(self.url + "/api/propose", data=body,
                      headers={"X-AppSort-Token": self.token, "Content-Type": "application/json"})
        data = json.loads(urlopen(req).read())
        self.assertEqual(data["proposal"]["capacity"], 1)
        self.assertEqual(data["proposal"]["page_limit"], 2)
        self.assertEqual(data["proposal"]["diff"]["pages_after"], 2)
        self.assertEqual(len(data["proposal"]["tail_folder"]["apps"]), 2)
        self.assertEqual(self.tool.adapter.writes, 0)


if __name__ == "__main__":
    unittest.main()
