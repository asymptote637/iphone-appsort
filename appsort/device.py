"""USB-only worker. Every connection is pinned to one explicitly selected UDID."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import plistlib
import sys
from pathlib import Path

from .core import SortError, apps


async def inventory() -> list[dict]:
    from pymobiledevice3.usbmux import list_devices
    from pymobiledevice3.lockdown import create_using_usbmux
    devices = []
    for mux in await list_devices():
        if mux.connection_type != "USB":
            continue
        row = {"udid": mux.serial, "connection": "USB"}
        try:
            phone = await create_using_usbmux(serial=mux.serial, autopair=False, connection_type="USB")
            try:
                values = phone.all_values
                row.update(name=values.get("DeviceName", "iPhone"), version=values.get("ProductVersion"),
                           model=values.get("ProductType"), build=values.get("BuildVersion"), ecid=hex(int(values.get("UniqueChipID", 0))),
                           trusted=True, device_class=values.get("DeviceClass"))
            finally:
                await phone.close()
        except Exception as error:
            row.update(trusted=False, error=type(error).__name__, name="未解锁或未信任的设备")
        devices.append(row)
    return devices


async def read(udid: str, icons_dir: Path | None = None) -> dict:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.springboard import SpringBoardServicesService
    phone = await create_using_usbmux(serial=udid, autopair=False, connection_type="USB")
    try:
        values = phone.all_values
        if values.get("UniqueDeviceID") != udid:
            raise SortError("连接到了不同设备，已停止。")
        async with SpringBoardServicesService(phone) as service:
            layout = await asyncio.wait_for(service.get_icon_state(), 20)
            missing = 0
            if icons_dir is not None:
                import hashlib
                icons_dir.mkdir(parents=True, exist_ok=True)
                for app in apps(layout):
                    identity = str(app.get("bundleIdentifier") or app.get("displayIdentifier") or "")
                    path = icons_dir / (hashlib.sha256(identity.encode()).hexdigest() + ".png")
                    if path.exists():
                        continue
                    try:
                        png = await asyncio.wait_for(service.get_icon_pngdata(identity), 2)
                        if png:
                            path.write_bytes(png)
                    except Exception:
                        missing += 1  # Missing artwork never changes the app list or write result.
        return {"raw": base64.b64encode(plistlib.dumps(layout, fmt=plistlib.FMT_BINARY)).decode(),
                "device": {"udid": udid, "name": values.get("DeviceName"), "version": values.get("ProductVersion"),
                           "model": values.get("ProductType"), "build": values.get("BuildVersion"), "ecid": hex(int(values.get("UniqueChipID", 0)))},
                "missing_icons": missing}
    finally:
        await phone.close()


async def native_write(udid: str, path: Path) -> dict:
    """Preserve raw widget objects. Success is decided only by a later independent read."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.springboard import SpringBoardServicesService
    layout = plistlib.loads(path.read_bytes())
    phone = await create_using_usbmux(serial=udid, autopair=False, connection_type="USB")
    try:
        if phone.all_values.get("UniqueDeviceID") != udid:
            raise SortError("连接到了不同设备，已停止。")
        async with SpringBoardServicesService(phone) as service:
            try:
                await asyncio.wait_for(service.set_icon_state(layout), 10)
                return {"sent": True, "acknowledged": True}
            except asyncio.TimeoutError:
                return {"sent": True, "acknowledged": False,
                        "note": "SpringBoard 未回复；必须读回后判断。"}
    finally:
        await phone.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("list", "read", "native-write"))
    parser.add_argument("--udid")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--icons", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "list":
            result = asyncio.run(asyncio.wait_for(inventory(), 25))
        elif args.action == "read":
            if not args.udid:
                raise SortError("缺少所选设备。")
            result = asyncio.run(read(args.udid, args.icons))
        else:
            if not args.udid or not args.file:
                raise SortError("写入参数不完整。")
            result = asyncio.run(native_write(args.udid, args.file))
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"error": str(error) or type(error).__name__, "type": type(error).__name__}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
