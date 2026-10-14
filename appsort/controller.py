"""Persistence and verified transactions. No automatic or unattended phone writes."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .core import SortError, apps, canonical, diff, fingerprint, is_widget, rank_layout, test_swap, to_cfgutil, validate,validate_options
from .usage import import_counts, read_usage, stream_devices

ROOT = Path(__file__).resolve().parents[1]


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def load_json(path: Path, default: object = None) -> object:
    return json.loads(path.read_text()) if path.exists() else default


def save_plist(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_bytes(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))
    os.chmod(temporary, 0o600)
    temporary.replace(path)


class DeviceAdapter:
    def worker(self, arguments: list[str], timeout: int = 35) -> object:
        try:
            completed = subprocess.run([sys.executable, "-m", "appsort.device", *arguments], cwd=ROOT,
                                       capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise SortError("与 iPhone 通信超时。请保持连接、解锁后重试；写入结果需重新读取确认。") from error
        try:
            result = json.loads(completed.stdout)
        except ValueError as error:
            raise SortError("设备通信没有返回有效结果：" + completed.stderr[-500:]) from error
        if completed.returncode or isinstance(result, dict) and result.get("error"):
            raise SortError("无法连接 iPhone：" + str(result.get("error", "未知错误")))
        return result

    def inventory(self) -> list[dict]:
        return self.worker(["list"])

    def read(self, udid: str, icons: Path | None = None) -> tuple[list, dict]:
        arguments = ["read", "--udid", udid]
        if icons:
            arguments += ["--icons", str(icons)]
        result = self.worker(arguments, 300 if icons else 35)
        return plistlib.loads(base64.b64decode(result["raw"])), result["device"]

    def write(self, device: dict, layout: list, state: Path, backend: str) -> dict:
        if backend == "native":
            path = state / "transaction.plist"
            save_plist(path, layout)
            return self.worker(["native-write", "--udid", device["udid"], "--file", str(path)])
        if backend != "cfgutil":
            raise SortError("写入接口无效。")
        tool = find_cfgutil()
        if not tool:
            raise SortError("请先在 Mac 安装 Apple Configurator，再退出其窗口。")
        if not device.get("ecid") or device["ecid"] == "0x0":
            raise SortError("不能确认所选设备的 ECID，已停止写入。")
        path = state / "transaction-cfgutil.json"
        save_json(path, to_cfgutil(layout))
        command = [tool, "--ecid", device["ecid"], "--format", "JSON", "set-icon-layout", str(path)]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=60, check=False)
            return {"exit_code": result.returncode, "stdout": result.stdout[-3000:], "stderr": result.stderr[-1000:]}
        except subprocess.TimeoutExpired:
            return {"timeout": True, "note": "cfgutil 超时；继续读回确认，不假定失败或成功。"}


def find_cfgutil() -> str | None:
    candidates = [Path("/Applications/Apple Configurator.app/Contents/MacOS/cfgutil"),
                  Path("/Applications/Apple Configurator 2.app/Contents/MacOS/cfgutil"),
                  Path.home() / "Applications/Apple Configurator.app/Contents/MacOS/cfgutil"]
    path = shutil.which("cfgutil")
    if path:
        candidates.insert(0, Path(path))
    return next((str(path) for path in candidates if path.is_file()), None)


class Organizer:
    def __init__(self, state: Path, adapter: DeviceAdapter | None = None, demo: bool = False):
        self.state = state.resolve()
        self.state.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state, 0o700)
        self.adapter = adapter or DeviceAdapter()
        self.demo = demo
        self.lock = threading.Lock()

    def current(self) -> list:
        path = self.state / "current.plist"
        if not path.exists():
            raise SortError("请先读取 iPhone。")
        return plistlib.loads(path.read_bytes())

    def device(self) -> dict:
        result = load_json(self.state / "device.json")
        if not result:
            raise SortError("请先选择并读取 iPhone。")
        return result

    def snapshot(self, layout: list, device: dict, reason: str) -> str:
        name = stamp() + "-" + reason
        path = self.state / "backups" / (name + ".plist")
        save_plist(path, layout)
        save_json(path.with_suffix(".json"), {"device": device, "hash": fingerprint(layout), "reason": reason})
        return name

    def read_phone(self, udid: str) -> dict:
        with self.lock:
            if self.demo:
                raise SortError("示例模式不能读取或修改手机。")
            devices = self.adapter.inventory()
            if udid not in {row["udid"] for row in devices if row.get("trusted")}:
                raise SortError("没有找到已信任的所选 USB 设备。")
            layout, device = self.adapter.read(udid)
            validate(layout)
            backup = self.snapshot(layout, device, "read")
            save_plist(self.state / "current.plist", layout)
            previous = load_json(self.state / "device.json", {})
            save_json(self.state / "device.json", device)
            if previous.get("udid") != device["udid"]:
                # Keep old evidence on disk for traceability, but stop using it for a different phone.
                save_json(self.state / "usage.json", {})
                save_json(self.state / "proposal.json", {})
            return {"message": "已读取手机并保存原始布局备份。", "backup": backup,
                    "device": device, "app_count": len(list(apps(layout)))}

    def copy_usage(self) -> dict:
        with self.lock:
            if self.demo:
                raise SortError("示例模式不能读取私人使用记录。")
            helper = ROOT / "bin/appsort-usage-helper"
            if not helper.exists():
                raise SortError("复制助手未编译，请运行 bin/setup 或双击 Setup AppSort.command。")
            result = subprocess.run([str(helper), str(self.state / "screentime")], capture_output=True,
                                    text=True, timeout=60, check=False)
            if result.returncode:
                # FDA is granted to the helper itself. A Terminal/Codex parent can
                # still inherit its own denial, so run an isolated one-off job.
                if platform.system() != "Darwin":
                    raise SortError(result.stderr.strip() or "复制使用记录失败。")
                self.copy_detached(helper, result.stderr.strip())
            devices = stream_devices(self.state / "screentime")
            if not devices:
                raise SortError("没有同步的 iPhone / iPad 记录。请确认同一 Apple ID 开启了跨设备共享。")
            return {"devices": devices, "message": "已复制记录，请选择与你手机对应的同步设备。"}

    def copy_detached(self, helper: Path, original_error: str) -> None:
        label = "local.appsort.copy." + uuid.uuid4().hex
        started = time.time_ns()
        copies = self.state / "screentime"
        marker = copies / "copied-at"
        # xpcproxy opens stdout before starting the FDA-authorized helper, so its
        # own logs must be outside Documents/Desktop privacy-protected folders.
        with tempfile.TemporaryDirectory(prefix="appsort-helper-") as temporary:
            out, err = Path(temporary) / "out", Path(temporary) / "err"
            out.touch(mode=0o600)
            err.touch(mode=0o600)
            job_path = Path(temporary) / "job.plist"
            job = {"Label": label, "ProgramArguments": [str(helper), str(copies)],
                   "RunAtLoad": True, "KeepAlive": False, "StandardOutPath": str(out), "StandardErrorPath": str(err)}
            save_plist(job_path, job)
            domain = f"gui/{os.getuid()}"
            command = ["/bin/launchctl", "bootstrap", domain, str(job_path)]
            submitted = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            if submitted.returncode:
                raise SortError(original_error + "\n独立助手启动失败：" + submitted.stderr.strip())
            try:
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if marker.exists() and marker.stat().st_mtime_ns >= started:
                        return
                    if err.stat().st_size:
                        raise SortError(err.read_text().strip())
                    time.sleep(0.2)
                raise SortError("助手没有完成复制。请检查完全磁盘访问权限；已停止本次任务。")
            finally:
                subprocess.run(["/bin/launchctl", "bootout", domain + "/" + label], capture_output=True, timeout=10, check=False)
                (self.state / "helper.out").write_text(out.read_text())
                (self.state / "helper.err").write_text(err.read_text())

    def collect(self, stream: str, days: int) -> dict:
        with self.lock:
            if self.demo:
                raise SortError("示例模式不能读取私人使用记录。")
            self.current()
            data = read_usage(self.state / "screentime", stream, days)
            data["phone_udid"] = self.device()["udid"]
            save_json(self.state / "usage.json", data)
            return {"message": "已统计打开或切回前台次数。", "usage": data}

    def import_usage(self, text: str, days: int) -> dict:
        with self.lock:
            data = import_counts(text, days, self.device()["udid"])
            save_json(self.state / "usage.json", data)
            return {"message": "已导入次数表。", "usage": data}

    def propose(self, options: dict) -> dict:
        with self.lock:
            data = load_json(self.state / "usage.json", {})
            if data.get("phone_udid") != self.device()["udid"]:
                raise SortError("使用记录不属于所选手机，请重新读取记录。")
            if self.demo and data.get("source") == "demo":
                # Fixed fictional values illustrate controls in either window.
                # Imported or synced evidence must always match its actual window.
                data["days"] = options.get("days", 7)
            proposal = rank_layout(self.current(), data, **options)
            if self.demo and data.get("source") == "demo":
                save_json(self.state / "usage.json", data)
            proposal["udid"] = self.device()["udid"]
            layout = proposal.pop("layout")
            save_plist(self.state / "proposal.plist", layout)
            proposal["proposal_hash"] = fingerprint(layout)
            proposal["created_at"] = datetime.now(timezone.utc).isoformat()
            proposal["diff"] = diff(self.current(), layout)
            save_json(self.state / "proposal.json", proposal)
            return {"message": "已生成排序预览，手机还没有变化。", "proposal": proposal}

    def capabilities(self) -> list[dict]:
        return load_json(self.state / "capabilities.json", [])

    def save_profile(self, name: str, options: dict) -> dict:
        with self.lock:
            name = name.strip()
            if not name or len(name) > 60:
                raise SortError("配置名称需为 1–60 个字符。")
            validate_options(options)
            allowed = {"metric", "days", "folders", "capacity", "widget_mode", "page_limit", "pinned"}
            if set(options) - allowed:
                raise SortError("配置包含不支持的字段。")
            profiles = load_json(self.state / "profiles.json", [])
            profiles = [profile for profile in profiles if profile['name'] != name]
            profiles.append({"name": name, "options": options, "saved_at": datetime.now(timezone.utc).isoformat()})
            save_json(self.state / "profiles.json", profiles)
            return {"message": "配置已保存在本机。"}

    def capable(self, backend: str) -> bool:
        device = self.device()
        return any(row.get("supported") and row.get("restored") and row.get("udid") == device["udid"]
                   and row.get("version") == device["version"] and row.get("backend") == backend
                   for row in self.capabilities())

    def transact(self, target: list, device: dict, backend: str, reason: str) -> dict:
        backup = self.snapshot(self.current(), device, reason)
        writer: dict
        try:
            writer = self.adapter.write(device, target, self.state, backend)
        except Exception as error:
            writer = {"error": str(error)}
        try:
            actual, actual_device = self.adapter.read(device["udid"])
            if actual_device["udid"] != device["udid"]:
                raise SortError("读回了不同的设备。")
            save_plist(self.state / "current.plist", actual)
            if canonical(actual) == canonical(target):
                status = "verified"
            elif canonical(actual) == canonical(plistlib.loads((self.state / "backups" / (backup + ".plist")).read_bytes())):
                status = "ignored"
            else:
                status = "partial"
            result = {"status": status, "writer": writer, "backup": backup,
                      "diff": diff(plistlib.loads((self.state / "backups" / (backup + ".plist")).read_bytes()), actual)}
        except Exception as error:
            result = {"status": "unverified", "writer": writer, "backup": backup, "error": str(error)}
        result.update(backend=backend, device=device, time=datetime.now(timezone.utc).isoformat())
        save_json(self.state / "transactions" / (stamp() + ".json"), result)
        save_json(self.state / "last-result.json", result)
        return result

    def check_write(self, backend: str) -> None:
        if self.demo:
            raise SortError("示例模式已禁用所有手机写入。")
        if backend not in ("native", "cfgutil"):
            raise SortError("请选择有效接口。")
        if backend == "cfgutil":
            if not find_cfgutil():
                raise SortError("未找到 Apple Configurator，请安装 Mac 版本并退出它。")
            to_cfgutil(self.current())  # Blocks lossy widget conversion.

    def test(self, backend: str, expected_hash: str) -> dict:
        with self.lock:
            self.check_write(backend)
            original, device = self.adapter.read(self.device()["udid"])
            if fingerprint(original) != expected_hash:
                raise SortError("手机布局已变化，请重新读取后再测试。")
            save_plist(self.state / "current.plist", original)
            trial, names = test_swap(original)
            result = self.transact(trial, device, backend, "before-test")
            if result["status"] == "verified":
                restore = self.transact(original, device, backend, "before-test-restore")
                restored = restore["status"] == "verified"
                result.update(restored=restored, restore=restore)
            else:
                # Even a partially applied transaction needs a best-effort restore.
                if result["status"] == "partial":
                    result["restore"] = self.transact(original, device, backend, "before-partial-restore")
                result["restored"] = result["status"] == "ignored" or result.get("restore", {}).get("status") == "verified"
            supported = result["status"] == "verified" and result["restored"]
            rows = self.capabilities()
            rows.append({"udid": device["udid"], "version": device["version"], "backend": backend,
                         "supported": supported, "restored": result["restored"], "time": result["time"]})
            save_json(self.state / "capabilities.json", rows)
            result.update(names=names, supported=supported)
            result["message"] = ("已验证交换图标，并恢复原布局；此接口可用于当前系统。" if supported
                                 else "未确认该接口可用，已阻止批量写入。请查看结果与恢复备份。")
            save_json(self.state / "last-result.json", result)
            return result

    def apply(self, backend: str, expected_proposal: str) -> dict:
        with self.lock:
            self.check_write(backend)
            if not self.capable(backend):
                raise SortError("该系统和接口还未通过交换图标与恢复测试，请先验证接口。")
            manifest = load_json(self.state / "proposal.json", {})
            if not manifest or manifest.get("udid") != self.device()["udid"]:
                raise SortError("没有属于当前手机的预览。")
            target = plistlib.loads((self.state / "proposal.plist").read_bytes())
            if fingerprint(target) != manifest.get("proposal_hash") or expected_proposal != manifest.get("proposal_hash"):
                raise SortError("预览已变化，请重新查看预览后应用。")
            live, device = self.adapter.read(self.device()["udid"])
            if fingerprint(live) != manifest["base_hash"]:
                raise SortError("预览之后手机布局发生变化，请重新读取并生成预览。")
            if device.get("version") != self.device().get("version"):
                raise SortError("手机系统版本已变化，请重新读取并验证接口。")
            validate(target, live, manifest["capacity"], allow_widget_move=manifest.get("widget_mode") == "separate")
            save_plist(self.state / "current.plist", live)
            result = self.transact(target, device, backend, "before-apply")
            messages = {"verified": "已应用排序，手机读回布局与预览一致。",
                        "ignored": "iOS 没有接受布局，手机排列未变化。",
                        "partial": "手机只应用了部分布局，请检查并恢复备份。",
                        "unverified": "无法读回确认，请保持连接并读取手机；备份已保存。"}
            result["message"] = messages[result["status"]]
            save_json(self.state / "last-result.json", result)
            return result

    def restore(self, name: str, backend: str) -> dict:
        with self.lock:
            self.check_write(backend)
            if Path(name).name != name or not name.endswith(".plist"):
                raise SortError("备份名称无效。")
            path = self.state / "backups" / name
            meta = load_json(path.with_suffix(".json"), {})
            device = self.device()
            if meta.get("device", {}).get("udid") != device["udid"]:
                raise SortError("该备份属于另一台手机，已停止恢复。")
            target = plistlib.loads(path.read_bytes())
            if fingerprint(target) != meta.get("hash"):
                raise SortError("备份校验未通过，已停止恢复。")
            live, live_device = self.adapter.read(device["udid"])
            if {app.get("bundleIdentifier") for app in apps(live)} != {app.get("bundleIdentifier") for app in apps(target)}:
                raise SortError("备份以来 App 清单已变化，不能完整恢复。")
            save_plist(self.state / "current.plist", live)
            result = self.transact(target, live_device, backend, "before-restore")
            result["message"] = "恢复完成并已读回确认。" if result["status"] == "verified" else "恢复未得到完整确认，请查看手机和结果。"
            save_json(self.state / "last-result.json", result)
            return result

    def view(self) -> dict:
        current_path, proposal_path = self.state / "current.plist", self.state / "proposal.plist"
        current = self.current() if current_path.exists() else None
        proposal = load_json(self.state / "proposal.json", {})
        layout = plistlib.loads(proposal_path.read_bytes()) if proposal and proposal_path.exists() else None
        device = load_json(self.state / "device.json", {})
        return {"demo": self.demo, "device": device, "current": current, "proposed": layout,
                "profiles": load_json(self.state / "profiles.json", []),
                "current_hash": fingerprint(current) if current else None, "proposal": proposal,
                "usage": load_json(self.state / "usage.json", {}), "cfgutil": bool(find_cfgutil()),
                "widgets": sum(is_widget(item) for page in (current or []) for item in page),
                "capabilities": self.capabilities(), "result": load_json(self.state / "last-result.json", {}),
                "backups": [{"name": path.name, "metadata": load_json(path.with_suffix(".json"), {})}
                            for path in sorted((self.state / "backups").glob("*.plist"), reverse=True)[:50]],
                "helper_path": str(ROOT / "bin/appsort-usage-helper")}
