"""CLI entry point. GUI and CLI share the same validation and transaction code."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime,timedelta,timezone
from pathlib import Path

from .controller import ROOT, Organizer, load_json, save_json, save_plist
from .core import SortError, apps
from .server import make_server


def demo_state(organizer: Organizer) -> None:
    previous = load_json(organizer.state / "device.json", {})
    if previous and previous.get("udid") != "demo":
        raise SortError("Demo refuses to overwrite real device state. Choose a separate --state directory.")
    labels = ['Messages','Notes','Maps','Music','Calendar','Photos','Mail','Weather',
              'Clock','Files','Books','Journal','Tasks','Fitness','Travel','Reader',
              'Podcasts','Shopping','Translate','Settings','Camera','Wallet','Sketch','Browser',
              'Phone','Chat','Web','Capture']
    names = [(name, 'com.example.' + name.lower()) for name in labels]
    items = [{"bundleIdentifier": identity, "displayIdentifier": identity, "displayName": name} for name, identity in names]
    widget = {"iconType":"custom","displayIdentifier":"demo-widget","gridSize":"medium","iconLists":[],
              "elements":[{"containerBundleIdentifier":"com.apple.mobilecal","widgetIdentifier":"demo.calendar","uniqueIdentifier":"demo-calendar"}]}
    folder = {"displayName": "Utilities", "iconLists": [items[8:12]]}
    save_plist(organizer.state / "current.plist", [items[-4:], [widget, *items[:8]], [folder, *items[12:24]]])
    save_json(organizer.state / "device.json", {"udid": "demo", "name": "Demo iPhone", "version": "Demo", "ecid": "0x0"})
    save_json(organizer.state / "usage.json", {"phone_udid": "demo", "source": "demo", "days": 7,
                                              "newest": None, "apps": {item["bundleIdentifier"]: {"opens": (i * 37 + 11) % 180 + 1, "seconds": (i + 1) * 503,
                                              "last_open":(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat()}
                                                                        for i, item in enumerate(items)}})
    organizer.propose({"metric":"opens","days":7,"capacity":8,"widget_mode":"separate"})


def main() -> None:
    parser = argparse.ArgumentParser(description="AppSort：按使用频率整理 iPhone 主屏幕")
    parser.add_argument("--state", type=Path, default=ROOT / "state")
    parser.add_argument("--demo", action="store_true", help="仅示例数据，禁用手机写入")
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8766)
    serve.add_argument("--no-browser", action="store_true")
    sub.add_parser("devices")
    sub.add_parser("status")
    read = sub.add_parser("read")
    read.add_argument("--udid", required=True)
    sub.add_parser("copy-usage")
    usage = sub.add_parser("usage")
    usage.add_argument("--stream", required=True)
    usage.add_argument("--days", type=int, choices=(7, 30), default=7)
    propose = sub.add_parser("propose")
    propose.add_argument("--metric", choices=("opens", "seconds","recent"), default="opens")
    propose.add_argument("--days", type=int, choices=(7, 30), default=7)
    propose.add_argument("--folders", choices=("flatten", "preserve"), default="flatten")
    propose.add_argument("--capacity", type=int, default=8)
    propose.add_argument("--page-limit",type=int,default=15)
    propose.add_argument("--pin", action="append", default=[], metavar="BUNDLE_ID", help="置顶 App；可重复指定")
    propose.add_argument("--widgets", choices=("keep", "separate"), default="separate")
    for action in ("test", "apply", "restore"):
        command = sub.add_parser(action)
        command.add_argument("--backend", choices=("native", "cfgutil"), default="native")
        command.add_argument("--yes", action="store_true", help="已查看预览并授权本次写入")
        if action == "restore":
            command.add_argument("--backup", required=True)
    args = parser.parse_args()
    state = args.state
    if args.demo and state == ROOT / "state":
        state = ROOT / "demo-state"
    organizer = Organizer(state, demo=args.demo)
    try:
        if args.demo:
            demo_state(organizer)
        if args.action == "serve":
            server = make_server(organizer, args.port)
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"AppSort 已启动：{url}\n关闭此终端或按 Ctrl+C 可停止。", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return
        if args.action == "devices":
            result = {"devices": [] if args.demo else organizer.adapter.inventory()}
        elif args.action == "status":
            view = organizer.view()
            result = {"device": view["device"], "apps": len(list(apps(view["current"] or []))),
                      "widgets": view["widgets"], "cfgutil": view["cfgutil"], "result": view["result"],
                      "usage_source": view["usage"].get("source"), "usage_days": view["usage"].get("days")}
        elif args.action == "read":
            result = organizer.read_phone(args.udid)
        elif args.action == "copy-usage":
            result = organizer.copy_usage()
        elif args.action == "usage":
            result = organizer.collect(args.stream, args.days)
        elif args.action == "propose":
            result = organizer.propose({"metric": args.metric, "days": args.days, "folders": args.folders,
                                        "capacity": args.capacity, "widget_mode": args.widgets,
                                        "page_limit": args.page_limit, "pinned": args.pin})
        else:
            if not args.yes:
                print("本次会写入手机图标布局。原始布局接口保留已读到的小组件记录，但不能保证系统的所有隐藏设置。")
                print("请先查看网页预览；测试会交换两个图标并恢复，排序会应用已保存的预览。")
                if input("确认本次操作请输入 应用：") != "应用":
                    raise SortError("已取消。")
            if args.action == "test":
                result = organizer.test(args.backend, organizer.view()["current_hash"])
            elif args.action == "apply":
                result = organizer.apply(args.backend, organizer.view()["proposal"].get("proposal_hash", ""))
            else:
                result = organizer.restore(args.backup, args.backend)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if isinstance(result, dict) and result.get("status") in ("ignored", "partial", "unverified"):
            sys.exit(2)
    except (SortError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
