"""Pure layout validation, stable usage ranking, and cfgutil conversion."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterator


class SortError(Exception):
    """A user-actionable failure; callers must not silently continue."""


def app_id(item: dict) -> str:
    return str(item.get("bundleIdentifier") or item.get("displayIdentifier") or "")


def is_widget(item: dict) -> bool:
    return bool(item.get("elements")) or item.get("iconType") in ("custom", "widget", "Widget", "stack")


def children(item: dict) -> list | None:
    return None if is_widget(item) else item.get("iconLists")


def apps(layout: list) -> Iterator[dict]:
    for page in layout:
        for item in page:
            if is_widget(item):
                continue
            if children(item) is not None:
                yield from apps(children(item))
            else:
                yield item


def key(item: dict) -> str:
    if item.get("isWebClip") or item.get("webClipURL"):
        return "url:" + str(item.get("webClipURL") or item.get("url") or "")
    return app_id(item)


def to_cfgutil(layout: list) -> list:
    """Strict conversion: unknown icon types are never silently discarded."""
    def convert(item: dict) -> Any:
        if is_widget(item):
            raise SortError("Apple Configurator 的布局格式无法保留现有小组件；请使用原始布局接口测试，或先自行移除小组件。")
        pages = children(item)
        if pages is not None:
            name = str(item.get("displayName") or "文件夹")
            converted = [[convert(icon) for icon in page] for page in pages if page]
            if not converted:
                raise SortError("布局含空文件夹，无法安全写入。")
            return [name, *converted[0]] if len(converted) == 1 else [name, *converted]
        identity = key(item)
        if identity.startswith("url:"):
            url = identity[4:]
            if not url.startswith(("https://", "http://")):
                raise SortError("有无法转换的网址图标。")
            return url
        if not identity or item.get("iconType") in ("widget", "Widget", "stack"):
            raise SortError("布局含无法识别的图标或小组件，已阻止写入。")
        return identity

    if not isinstance(layout, list) or not layout:
        raise SortError("没有有效的主屏幕布局。")
    if any(not isinstance(page, list) for page in layout):
        raise SortError("主屏幕格式无法识别。")
    return [[convert(item) for item in page] for page in layout]


def canonical(layout: list) -> list:
    """Compare position, folder membership and names; ignore transient icon metadata."""
    def entry(item: dict) -> Any:
        if is_widget(item):
            return {"widget": item.get("displayIdentifier"), "size": item.get("gridSize"),
                    "elements": [{k: value for k, value in element.items() if k != "iconModDate"}
                                 for element in item.get("elements", [])],
                    "selected": item.get("userSelectedElementIdentifier")}
        if children(item) is not None:
            return {"folder": item.get("displayName"), "pages": canonical(children(item))}
        return key(item)
    return [[entry(item) for item in page] for page in layout]


def fingerprint(layout: list) -> str:
    raw = json.dumps(canonical(layout), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def validate(layout: list, reference: list | None = None, capacity: int = 24, allow_widget_move: bool = False) -> None:
    if not isinstance(layout, list) or not layout or any(not isinstance(page, list) for page in layout):
        raise SortError("主屏幕布局格式无法识别。")
    def check(pages: list) -> None:
        for page in pages:
            for item in page:
                if not isinstance(item, dict):
                    raise SortError("有无法识别的空位或图标类型，已停止写入。")
                if is_widget(item):
                    if not item.get("displayIdentifier") or item.get("gridSize") not in ("small", "medium", "large"):
                        raise SortError("小组件格式未知，已停止写入。")
                elif children(item) is not None:
                    if not children(item) or not any(children(item)):
                        raise SortError("布局含空文件夹。")
                    check(children(item))
                elif not key(item):
                    raise SortError("图标没有有效的标识。")
    check(layout)
    if len(layout[0]) > 4:
        raise SortError("Dock 最多容纳 4 个图标。")
    if any(children(item) is not None for item in layout[0]):
        raise SortError("暂不支持 Dock 中有文件夹的布局。")
    if any(sum(widget_slots(item) for item in page) > 24 for page in layout[1:]):
        raise SortError("有页面超过容量，请调整每页数量。")
    if any(sum(not is_widget(item) for item in page) > capacity for page in layout[1:]):
        raise SortError("有页面超过所选 App 数量上限。")
    ids = [key(item) for item in apps(layout)]
    if len(set(ids)) != len(ids):
        raise SortError("布局有重复图标；当前版本不改动这种布局。")
    if reference is not None:
        expected = Counter(key(item) for item in apps(reference))
        if Counter(ids) != expected:
            raise SortError("草稿与当前手机的图标清单不同，请重新读取手机并生成预览。")
        if [key(item) for item in layout[0]] != [key(item) for item in reference[0]]:
            raise SortError("Dock 已变化，请重新读取手机。")
        original_widgets = [(page_no, slot, item) for page_no, page in enumerate(reference)
                            for slot, item in enumerate(page) if is_widget(item)]
        changed_widgets = [(page_no, slot, item) for page_no, page in enumerate(layout)
                           for slot, item in enumerate(page) if is_widget(item)]
        if allow_widget_move:
            original_map = {item["displayIdentifier"]: item for _, _, item in original_widgets}
            changed_map = {item["displayIdentifier"]: item for _, _, item in changed_widgets}
            widget_match = (original_map == changed_map and len(original_widgets) == len(changed_widgets)
                            and len(changed_map) == len(changed_widgets))
        else:
            widget_match = original_widgets == changed_widgets
        if not widget_match:
            raise SortError("小组件位置或内容已变化，已停止写入。")


def widget_slots(item: dict) -> int:
    return {"small": 4, "medium": 8, "large": 16}.get(item.get("gridSize"), 24) if is_widget(item) else 1


def recent_epoch(row: dict) -> float:
    value = row.get("last_open")
    if not value:
        return 0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.timestamp()
    except (ValueError, TypeError, OverflowError):
        raise SortError("最近使用记录的时间格式无效。") from None


def validate_options(options: dict) -> None:
    if not isinstance(options, dict):
        raise SortError("配置格式无效。")
    if options.get("metric", "opens") not in ("opens", "seconds", "recent") or options.get("days", 7) not in (7, 30):
        raise SortError("排序参数无效。")
    capacity = options.get("capacity", 8)
    limit = options.get("page_limit", 15)
    if type(capacity) is not int or not 1 <= capacity <= 24 or type(limit) is not int or not 1 <= limit <= 15:
        raise SortError("每页图标需为 1–24 个；页面上限需为 1–15 页。")
    if options.get("folders", "flatten") not in ("flatten", "preserve") or options.get("widget_mode", "separate") not in ("keep", "separate"):
        raise SortError("布局参数无效。")
    pins = options.get("pinned", [])
    if not isinstance(pins, list) or any(not isinstance(item, str) or not item for item in pins) or len(set(pins)) != len(pins):
        raise SortError("置顶清单无效。")


def rank_layout(current: list, usage: dict, metric: str = "opens", days: int = 7,
                folders: str = "flatten", capacity: int = 24, pinned: list[str] | None = None,
                widget_mode: str = "keep", page_limit: int = 15) -> dict:
    pinned = [] if pinned is None else pinned
    validate_options({"metric": metric, "days": days, "capacity": capacity, "folders": folders,
                      "widget_mode": widget_mode, "page_limit": page_limit, "pinned": pinned})
    validate(current)
    stats = usage.get("apps", {})
    if usage.get("days") != days:
        raise SortError("使用记录的统计周期不同，请重新读取该周期的记录。")
    known = {app_id(item) for item in apps(current)}
    if not any(identity in known and (recent_epoch(row) if metric == "recent" else row.get(metric, 0)) > 0
               for identity, row in stats.items()):
        label = {"opens": "打开次数", "seconds": "使用时长", "recent": "最近使用"}[metric]
        raise SortError(f"还没有这台 iPhone 的{label}记录，不能生成有依据的排序。")
    if len(set(pinned)) != len(pinned) or set(pinned) - known:
        raise SortError("置顶 App 清单无效。")
    pin_order = {identity: index for index, identity in enumerate(pinned)}

    def value(item: dict, field: str) -> float:
        if field == "recent":
            return max((recent_epoch(stats.get(app_id(app), {})) for app in apps([[item]])), default=0)
        return sum(float(stats.get(app_id(app), {}).get(field, 0))
                   for app in apps([[item]]))

    def score(item: dict) -> tuple:
        identifiers = [app_id(app) for app in apps([[item]])]
        pins = [pin_order[identity] for identity in identifiers if identity in pin_order]
        secondary = "seconds" if metric == "opens" else "opens"
        return (0 if pins else 1, min(pins) if pins else 0, -value(item, metric), -value(item, secondary))

    source = copy.deepcopy(current)
    if folders == "flatten":
        items = list(apps(source[1:]))
    else:
        items = [item for page in source[1:] for item in page if not is_widget(item)]
        for item in items:
            if children(item) is not None:
                inner = sorted(apps(children(item)), key=score)
                item["iconLists"] = [inner[index:index + 9] for index in range(0, len(inner), 9)]
    items.sort(key=score)  # Equal scores retain original order, preventing unnecessary movement.
    all_widgets = [item for page in source[1:] for item in page if is_widget(item)]
    tail_folder = None
    # Respect the selected page budget by grouping only the necessary tail.
    # Fifteen is a conservative default based on the tested phone's normalization.
    if widget_mode == "separate":
        available_pages = page_limit - (1 if all_widgets else 0)
        maximum_icons = available_pages * capacity
    else:
        if any(i >= page_limit and any(is_widget(item) for item in page) for i, page in enumerate(source[1:])):
            raise SortError("要保留的小组件页超过页面上限，请提高上限或独立放置小组件。")
        lost = sum(max(0, capacity - min(capacity, 24 - sum(widget_slots(i) for i in page if is_widget(i))))
                   for page in source[1:])
        maximum_icons = page_limit * capacity - lost
    if items and maximum_icons < 1:
        raise SortError("页面预算没有为 App 留出空间。")
    if len(items) > maximum_icons:
        group_count = len(items) - maximum_icons + 1
        tail = items[-group_count:]
        if any(children(item) is not None for item in tail):
            raise SortError("页面预算不足以保留文件夹，请提高上限或展开文件夹后重试。")
        tail_folder = {"name": "末尾 App", "apps": [item.get("displayName", app_id(item)) for item in tail]}
        folder = {"displayName": tail_folder["name"], "iconLists": [tail[i:i + 9] for i in range(0, len(tail), 9)]}
        items = [*items[:-group_count], folder]
    proposed = [source[0]]
    remaining = items[:]
    if widget_mode == "separate" and all_widgets:
        if sum(widget_slots(item) for item in all_widgets) > 24:
            raise SortError("现有小组件放不进一页，请选择保留原位。")
        proposed.append(all_widgets)
    for page in (source[1:] if widget_mode == "keep" else []):
        widgets = {slot: item for slot, item in enumerate(page) if is_widget(item)}
        room = min(capacity, 24 - sum(widget_slots(item) for item in widgets.values()))
        if room < 0:
            raise SortError("该每页容量放不下原有小组件，请选择更大的容量。")
        selected, remaining = remaining[:room], remaining[room:]
        result = []
        if widgets and max(widgets) >= len(selected) + len(widgets):
            raise SortError("排序后无法保留小组件原有位置，已停止生成。")
        for slot in range(len(selected) + len(widgets)):
            result.append(widgets[slot] if slot in widgets else selected.pop(0))
        if any(slot >= len(result) for slot in widgets):
            raise SortError("排序后无法保留小组件原有位置，已停止生成。")
        if result or widgets:
            proposed.append(result)
        elif remaining:
            proposed.append([])
    while remaining:
        proposed.append(remaining[:capacity])
        remaining = remaining[capacity:]
    if len(proposed) == 1:
        proposed.append([])
    if len(proposed) - 1 > page_limit:
        raise SortError("保留原位置后页数仍超过上限，请选择独立小组件页。")
    validate(proposed, current, capacity, allow_widget_move=widget_mode == "separate")
    return {"layout": proposed, "base_hash": fingerprint(current), "metric": metric,
            "days": days, "folders": folders, "capacity": capacity, "pinned": pinned,
            "widget_mode": widget_mode, "tail_folder": tail_folder,
            "page_limit": page_limit,
            "source": usage.get("source"), "newest": usage.get("newest")}


def diff(before: list, after: list) -> dict:
    def positions(layout: list) -> dict:
        found = {}
        def walk(pages: list, prefix: str) -> None:
            for page_index, page in enumerate(pages):
                for slot, item in enumerate(page):
                    position = f"{prefix}/{page_index}/{slot}"
                    if is_widget(item):
                        continue
                    if children(item) is not None:
                        walk(children(item), position + "/" + str(item.get("displayName", "")))
                    else:
                        found[key(item)] = (position, item.get("displayName", key(item)))
        walk(layout, "")
        return found
    old, new = positions(before), positions(after)
    moved = [{"id": identity, "name": new[identity][1]} for identity in new
             if identity not in old or old[identity][0] != new[identity][0]]
    return {"moved": moved, "count": len(moved), "pages_before": len(before) - 1,
            "pages_after": len(after) - 1}


def test_swap(layout: list) -> tuple[list, list[str]]:
    trial = copy.deepcopy(layout)
    for page in trial[1:]:
        slots = [i for i, item in enumerate(page) if children(item) is None and not is_widget(item)]
        if len(slots) >= 2:
            a, b = slots[:2]
            page[a], page[b] = page[b], page[a]
            validate(trial, layout)
            return trial, [page[a].get("displayName", key(page[a])), page[b].get("displayName", key(page[b]))]
    raise SortError("找不到同一页的两个独立图标来测试；可以直接预览排序。")
