#!/usr/bin/env python3
"""Generate a static, synthetic-only browser demo from the real UI."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from appsort.controller import Organizer
from appsort.__main__ import demo_state

TRANSLATIONS={
 '常用的，放前面。':'Your favorites. Up front.',
 '按使用记录整理 iPhone，把布局调成你喜欢的样子。':'Arrange by usage. Make the layout your own.',
 '导出排序记录 ↗':'Export preview ↗','只在本机处理':'Synthetic demo',
 '主屏幕 App':'Home Screen apps','当前页面':'Current pages','天统计周期':'Day window',
 '连接 iPhone':'Connect iPhone','读取使用频率':'Read usage','排列方式':'Arrange',
 '用 USB 连接、解锁，并信任这台 Mac。':'Connect, unlock and trust your Mac for the desktop app.',
 '选择 USB 设备':'USB device','刷新设备':'Refresh','读取布局':'Read layout',
 '统计周期':'Usage window','最近 7 天':'Last 7 days','最近 30 天':'Last 30 days',
 '读取同步记录':'Read synced records','首次设置与数据说明':'Setup & data details',
 '导入已有次数表':'Import app counts','优先顺序':'Sort by',
 '打开次数多的在前':'Most opened first','使用时长长的在前':'Most time first',
 '文件夹':'Folders','展开文件夹，全部按频率排':'Flatten and rank apps',
 '保留文件夹，内外都按频率排':'Keep and rank folders',
 '小组件页面':'Widget placement','单独放在第一页':'Dedicated first page',
 '保留原来的页面与位置':'Keep current positions','每页 App 图标数量':'Icons per app page',
 '8 个 · 顶部两行':'8 · top two rows','16 个 · 四行':'16 · four rows',
 '20 个 · 五行':'20 · five rows','24 个 · 六行':'24 · six rows',
 '生成排序预览':'Generate preview','排序预览':'Proposed','现在的排列':'Current',
 '准备好了，再应用。':'Preview first. Apply when ready.',
 '验证交换与恢复':'Test swap & restore','应用到 iPhone':'Apply to iPhone',
 '写入方式与备份恢复':'Write method & backups','使用排名':'Usage ranking',
 '小组件叠放':'Widget stack','示例数据 · 仅用于体验':'Synthetic data · demo only',
 '当前是示例数据。可以体验生成预览，所有手机读写已禁用。':'Interactive demo: all data is fictional. Phone reads and writes are disabled.',
 'Dock 固定。小组件独立一页；App 页面只排顶部两行。超出 15 页时把排名末尾的 App 合入最后一个文件夹。':'Dock stays fixed. Widgets get their own page. App pages use the top two rows; the lowest-ranked tail is grouped when needed.',
 'AppSort 0.1 · 排序、备份和记录均保存在本地':'AppSort 0.1 · local layouts, usage and backups',
 '每次写入都先备份，再读回确认':'Back up before writing. Verify by reading back.',
 '接口待验证':'Desktop-only write test','先验证交换与恢复；系统拒绝写入时不会报成功。':'Phone writes are disabled in this online demo.',
 '按打开或切回前台次数。':'Observed foreground activations.',
 '☆ 置顶会优先于自动排名；Dock 中的 App 保持原位置。':'☆ pins an app ahead of ranking. Dock positions stay fixed.',
 '布局预设':'Layout preset','顶部两行 · 次数优先':'Two rows · most opened',
 '完整页面 · 充分利用空间':'Full pages · use the space',
 '保留文件夹 · 时长优先':'Keep folders · most time',
 '最近使用 · 顶部三行':'Recent apps · three rows','自定义':'Custom',
 '最近使用的在前':'Recently used first','每页图标数量':'Icons per page','总页面上限':'Page budget',
 '保存与加载本地配置':'Save & load local profiles','已保存的配置':'Saved profiles',
 '选择本地配置':'Choose a local profile','配置名称':'Profile name','例如：工作日':'e.g. Weekdays',
 '保存当前设置':'Save settings','同名保存会更新设置；加载后请重新生成预览。':'Saving the same name updates it. Generate a new preview after loading.',
 '搜索 App 名称或标识':'Search apps or bundle IDs','导出使用表 CSV':'Export usage CSV','清除置顶':'Clear pins',
 '没有匹配的 App，或尚未读取手机。':'No matching apps, or no layout yet.',
 '按累计使用时长。':'Accumulated foreground time.',
 '按最后一次前台记录；无记录的 App 保留相对顺序。':'Latest foreground record. Unobserved apps retain their relative order.',
 '排列方式已变，请重新生成预览。':'Settings changed. Generate a new preview.',
 '已加载设置，请生成新预览。':'Profile loaded. Generate a new preview.',
 '导入当前周期':'Import this window','原始布局备份':'Layout backups','恢复所选布局':'Restore selected layout',
 '原始布局接口 · 保留小组件记录':'Native layout · keep widget records',
 'Apple Configurator · 无小组件布局':'Apple Configurator · no widgets',
 '写入接口':'Write backend','暂无备份':'No backups','未检测到 USB 设备':'No USB devices in demo',
 '选择对应的同步设备':'Synced device','确认名称与这台 iPhone 一致，避免混入旧手机或 iPad。':'Match the phone name; old devices can remain in the list.',
 '统计这个设备':'Calculate this device','请确认对应的同步设备':'Choose the matching device',
 '手机与 Mac 使用同一 Apple ID，并开启屏幕使用时间的“在设备之间共享”。首次同步可能需要数小时。':'Use the same Apple ID on phone and Mac. Enable Screen Time Share Across Devices. First sync may take hours.',
 '复制助手需要完全磁盘访问权限。添加下列文件即可，无需给终端授权：':'Grant the compiled copy helper Full Disk Access in macOS settings:',
 '次数表示 App 打开或切回前台，包含恢复使用，不等于进程冷启动次数。首次写入可能让仅在 App 资源库的 App 回到主屏幕；工具会检测这种变化并停止旧预览。':'Opens include returning to an app. The first phone write may return App Library Only apps to the Home Screen; an inventory change blocks the stale preview.',
 '粘贴 CSV，表头为 bundle_id,opens，可加 seconds,last_open。最近使用时间需含时区，例如 2026-01-01T08:00:00+08:00。':'Desktop CSV: bundle_id,opens, with optional seconds,last_open. Timestamps must include a timezone, e.g. 2026-01-01T08:00:00+08:00.',
 '次数 CSV':'Usage CSV','备份是图标布局，不是完整手机备份。隐藏页等系统状态无法保证恢复。成功以手机读回结果为准。':'Layout backups are not full phone backups. Hidden-page state may not restore. Success requires reading the phone back.',
 '正在处理，请保持手机连接…':'Working…','先读取手机，再生成预览。手机不会自动改变。':'Read a layout, then preview. The phone does not change automatically.',
 '先验证手机是否接受布局，再应用已保存的预览。':'Test the phone backend, then apply the saved preview.',
 '已应用到 iPhone':'Applied to iPhone','当前系统已验证':'Backend verified',
 'Dock 固定。每页最多 ':'Dock fixed. Up to ',' 个图标；':' icons per page; ',
 '小组件独立第一页。':'widgets on their own first page. ',
 '小组件保留原位。':'widgets stay in place. ','最多 ':'Budget: ',
 ' 页，必要时合并末尾 App。':' pages; group the smallest tail if needed.',
 '检测到 ':'Found ',' 个小组件 / 叠放。按所选方式保留完整记录；Apple Configurator 路线已禁用，避免丢失它们。':' widget stack. Widget records follow your policy; the Configurator route is blocked for this layout.',
 ' 个 App 位置变化 · ':' apps move · ',' 页 · Dock 固定':' pages · Dock fixed',
 ' · 末尾 ':' · tail: ',' 个 App 合入文件夹':' apps grouped',
 ' · 记录周期 ':' · window: ',' · 请重新读取所选周期':' · select this window again in the desktop app',
 '最近 ':'Last ',' 天':' days','第 ':'Page ',' 页':' page','当前':'current','预览':'preview',
 '尚未读取手机':'No layout read','保留原始记录与位置':'Original widget records',
 '日历':'Calendar','照片':'Photos','电池':'Batteries','天气':'Weather','地图':'Maps','备忘录':'Notes',
 '上一页':'Previous page','下一页':'Next page','置顶 ':'Pin ',
}

HANDLER=r'''async function api(path,body){
  if(path==='/api/state'||path==='/api/export')return structuredClone(DEMO_DATA);
  if(path==='/api/devices')return {devices:[]};
  if(path==='/api/propose'){
    const result=demoPropose(DEMO_DATA,body||{});
    DEMO_DATA.proposed=result.layout;DEMO_DATA.proposal=result.proposal;
    DEMO_DATA.usage.days=body?.days||7;
    return {message:'Synthetic preview updated. Phone reads and writes are disabled.'};
  }
  if(path==='/api/profile'){
    let name=String(body?.name||'').trim();
    if(!name||name.length>60)throw Error('Use a profile name between 1 and 60 characters.');
    demoPropose(DEMO_DATA,body.options);
    DEMO_DATA.profiles=(DEMO_DATA.profiles||[]).filter(p=>p.name!==name);
    DEMO_DATA.profiles.push({name,options:structuredClone(body.options)});
    try{localStorage.setItem('appsort-demo-profiles-v1',JSON.stringify(DEMO_DATA.profiles));}catch(error){/* Profiles remain available for this tab if browser storage is disabled. */}
    return {message:'Demo profile saved in this browser.'};
  }
  throw Error('The online demo cannot read a device, collect real usage, or write a phone. Download AppSort for macOS.');
}'''

def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        tool=Organizer(Path(temporary),demo=True)
        demo_state(tool)
        data=tool.view()
        data['helper_path']='Desktop download: bin/appsort-usage-helper'
        data['device']['name']='Demo iPhone'
        data['device']['version']='Demo'
        data['cfgutil']=False
    html=(ROOT/'web/index.html').read_text()
    setup_start=html.index('<div class="section"><h2><span class="step">01</span>')
    setup_end=html.index('<div class="section"><h2><span class="step">03</span>',setup_start)
    html=html[:setup_start]+'<details class="section"><summary>Mac &amp; USB setup</summary>'+html[setup_start:setup_end]+'</details>'+html[setup_end:]
    start=html.index('async function api(path,body)')
    end=html.index('\nasync function run(',start)
    html=html[:start]+HANDLER+html[end:]
    logic=(ROOT/'scripts/demo_logic.js').read_text()
    startup="\ntry{const profiles=JSON.parse(localStorage.getItem('appsort-demo-profiles-v1')||'[]');if(Array.isArray(profiles))DEMO_DATA.profiles=profiles;}catch(error){}\n"
    html=html.replace("const TOKEN='__SESSION_TOKEN__';","const TOKEN='public-demo';\nconst DEMO_DATA="+json.dumps(data,ensure_ascii=False,default=str)+';'+startup+logic)
    html=html.replace('async function artwork(id,node){','async function artwork(id,node){return;')
    for original,english in sorted(TRANSLATIONS.items(),key=lambda pair:-len(pair[0])):
        html=html.replace(original,english)
    html=html.replace('lang="zh-CN"','lang="en"').replace('"Songti SC","STSong",serif','Georgia,"Songti SC",serif')
    html=html.replace('<button class="full small" id="import">','<button class="full small" id="import" disabled>')
    html=html.replace('AppSort · 常用的，放前面','AppSort · Arrange by usage')
    html=html.replace("+' 次'","+' opens'").replace("'第 '+(page+1)+' / '","'Page '+(page+1)+' / '")
    html=html.replace("+' page'","+' pages'")
    output=ROOT/'docs/demo/index.html';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html)
    (ROOT/'docs/.nojekyll').touch()
    (ROOT/'docs/index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=demo/"><title>AppSort demo</title><a href="demo/">Open AppSort demo</a>')
    print(output)

if __name__=='__main__':
    main()
