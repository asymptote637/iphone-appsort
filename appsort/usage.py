"""Adapted from homescreen-organizer's MIT Biome collector; count foreground entries.

Counts are observed foreground activations (including returns), not OS process launches.
Only the explicitly selected synced iPhone stream is used.
"""
from __future__ import annotations

import csv
import io
import json
import math
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import SortError

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FocusChange:
    bundle_id: str
    at: datetime
    to_front: bool


def varint(data: bytes, at: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if at >= len(data):
            raise ValueError("truncated varint")
        byte = data[at]
        at += 1
        value |= (byte & 0x7f) << shift
        if byte < 0x80:
            return value, at
    raise ValueError("invalid varint")


def decoded(data: bytes) -> FocusChange | None:
    fields = {}
    at = 0
    try:
        while at < len(data):
            tag, at = varint(data, at)
            number, wire = tag >> 3, tag & 7
            if not number:
                return None
            if wire == 0:
                fields[number], at = varint(data, at)
            elif wire == 1:
                fields[number] = struct.unpack_from("<d", data, at)[0]
                at += 8
            elif wire == 2:
                length, at = varint(data, at)
                if length > len(data) - at:
                    return None
                fields[number] = data[at:at + length]
                at += length
            elif wire == 5:
                at += 4
                if at > len(data):
                    return None
            else:
                return None
        timestamp = fields.get(4)
        identity = fields.get(6)
        flag = fields.get(3)
        if not isinstance(timestamp, float) or not math.isfinite(timestamp):
            return None
        if not isinstance(identity, bytes) or flag not in (0, 1):
            return None
        bundle = identity.decode("utf-8")
        if not bundle:
            return None
        return FocusChange(bundle, APPLE_EPOCH + timedelta(seconds=timestamp), bool(flag))
    except (ValueError, IndexError, UnicodeError, struct.error, OverflowError):
        return None


def aggregate(changes: list[FocusChange], since: datetime, until: datetime) -> dict:
    """Deduplicate synced records and bound durations at the last observed event.

An unclosed final session is not extended to now: an hours-old sync must not
invent hours of usage. The lookback boundary still includes an earlier open.
"""
    events = sorted(set(changes), key=lambda e: (e.at, e.to_front, e.bundle_id))
    seconds: defaultdict[str, float] = defaultdict(float)
    opens: Counter[str] = Counter()
    active: str | None = None
    start: datetime | None = None
    for event in events:
        if event.at > until:
            continue
        if event.to_front and event.bundle_id == active:
            continue
        if active is not None and start is not None and (event.to_front or event.bundle_id == active):
            begin, end = max(start, since), min(event.at, until)
            if end > begin:
                seconds[active] += (end - begin).total_seconds()
        if event.to_front:
            active, start = event.bundle_id, event.at
            if since <= event.at <= until:
                opens[event.bundle_id] += 1
        elif event.bundle_id == active:
            active, start = None, None
    return {identity: {"opens": opens[identity], "seconds": round(seconds[identity], 3)}
            for identity in sorted(set(opens) | set(seconds))}


def stream_devices(copies: Path) -> list[dict]:
    metadata = copies / "devices.json"
    if not metadata.exists():
        raise SortError("请先读取使用记录；复制助手需要完全磁盘访问权限。")
    rows = json.loads(metadata.read_text())
    root = copies / "App.InFocus"
    found = []
    for row in rows:
        identity = str(row.get("device_identifier", ""))
        if str(row.get("platform")) != "2" or not identity:
            continue
        if Path(identity).name != identity:
            continue
        folder = root / identity
        if folder.is_dir():
            name = str(row.get("name") or row.get("device_name") or "").strip()
            model = row.get("model")
            if not name:
                name = "iPhone / iPad" + (" · " + model if isinstance(model, str) and model.strip() else " · 历史设备")
            found.append({"id": identity,
                          "name": name,
                          "last_sync": row.get("last_sync_date"), "metadata": row})
    return found


def read_usage(copies: Path, device_id: str, days: int, now: datetime | None = None) -> dict:
    import ccl_segb
    if days not in (7, 30):
        raise SortError("统计周期只能是 7 或 30 天。")
    candidates = {row["id"] for row in stream_devices(copies)}
    if device_id not in candidates:
        raise SortError("请选择对应的同步 iPhone，不能混用其他设备的记录。")
    now = now or datetime.now(timezone.utc)
    changes: list[FocusChange] = []
    errors = []
    for path in sorted((copies / "App.InFocus" / device_id).iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            for record in ccl_segb.read_segb_file(str(path)):
                event = decoded(getattr(record, "data", b""))
                if event and event.at <= now + timedelta(minutes=5):
                    changes.append(event)
        except (OSError, ValueError, RuntimeError, struct.error, EOFError) as error:
            errors.append(f"{path.name}: {type(error).__name__}")
    if not changes:
        raise SortError("没有可解析的前台记录。请确认同一 Apple ID 已开启跨设备共享；iOS 27 的记录格式也可能已变化。")
    # Partial/corrupt sources must never yield a seemingly complete rank.
    if errors:
        raise SortError("部分使用记录无法解析，已停止排名：" + "; ".join(errors[:3]))
    since = now - timedelta(days=days)
    in_window = [event.at for event in changes if since <= event.at <= now]
    if not in_window:
        raise SortError("所选周期内没有使用记录；请等待手机同步后重试。")
    stats = aggregate(changes, since, now)
    for event in sorted(set(changes), key=lambda event: event.at):
        if event.to_front and since <= event.at <= now:
            stats.setdefault(event.bundle_id, {"opens": 0, "seconds": 0})["last_open"] = event.at.isoformat()
    return {"source": "biome_foreground", "metric_label": "打开或切回前台次数",
            "device_id": device_id, "days": days, "since": since.isoformat(), "until": now.isoformat(),
            "newest": max(in_window).isoformat(), "oldest": min(in_window).isoformat(),
            "record_count": len(set(changes)), "apps": stats,
            "note": "计数包含切回前台，不等于冷启动次数；记录可能晚于手机实时活动数小时。"}


def import_counts(text: str, days: int, device_udid: str) -> dict:
    """An explicit offline fallback; never treat imported totals as synced evidence."""
    if days not in (7, 30):
        raise SortError("统计周期无效。")
    table = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not {"bundle_id", "opens"}.issubset(table.fieldnames or []):
        raise SortError("CSV 表头需要 bundle_id,opens，可另加 seconds,last_open。")
    rows = {}
    try:
        for row in table:
            identity = row["bundle_id"].strip()
            count = int(row["opens"])
            seconds = float(row.get("seconds") or 0)
            if not identity or identity in rows or count < 0 or seconds < 0 or not math.isfinite(seconds):
                raise ValueError()
            rows[identity] = {"opens": count, "seconds": seconds}
            if row.get("last_open"):
                date = datetime.fromisoformat(row["last_open"].replace("Z", "+00:00"))
                if date.tzinfo is None:
                    raise ValueError()
                rows[identity]["last_open"] = date.isoformat()
    except (ValueError, TypeError, KeyError):
        raise SortError("CSV 含重复标识、负数、无效数字或没有时区的 last_open 时间。") from None
    if not rows:
        raise SortError("CSV 没有数据。")
    return {"source": "imported_csv", "days": days, "phone_udid": device_udid,
            "newest": None, "apps": rows, "note": "用户导入的次数；其统计范围由用户确认。"}
