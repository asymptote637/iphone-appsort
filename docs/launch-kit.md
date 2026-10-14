# AppSort launch kit

These are drafts for the maintainer to edit and publish. No community posts or messages are sent by AppSort. Choose a relevant community, check its current self-promotion rules, explain the use case, and respond to actual questions. There is no promised star count or Trending threshold.

Repository: https://github.com/asymptote637/iphone-appsort

Demo: https://asymptote637.github.io/iphone-appsort/demo/

Release: https://github.com/asymptote637/iphone-appsort/releases/tag/v0.1.0

## 30-second demonstration

1. Open the synthetic demo. Switch from the current layout to the proposed one.
2. Select Two rows, generate the preview, then advance past the widget page to show eight icons.
3. Try Full pages and Recent apps. Search for Messages, pin it, and generate again.
4. Save a named profile and export the CSV.
5. Point out that online phone writes are disabled. Real USB changes require the Mac download and a live swap/restore test.

Use `docs/assets/demo.jpg` when an image is needed. It contains fictional app data. Do not post personal Home Screen images or usage exports as promotion assets.

## Show HN draft

**Title:** Show HN: AppSort – preview and arrange an iPhone Home Screen by usage

Dragging many iPhone icons into a useful order is tedious. AppSort is a local Mac tool that turns observed app usage into a reviewable layout, then verifies phone writes by reading them back.

It ranks by opens, accumulated time or recency; supports editable presets, custom page density, folders, widget policies, pins and local profiles. A synthetic browser demo lets you try the planner without connecting a phone: https://asymptote637.github.io/iphone-appsort/demo/

Native layout writes were checked on one iPhone 17 / iOS 27.0. This is experimental device integration: other systems need their own swap/restore test, and the first write may bring library-only apps onto the Home Screen. The source, limitations, tests and installation instructions are at https://github.com/asymptote637/iphone-appsort.

Feedback on the preview workflow and anonymized compatibility reports would be useful.

## 中文社区草稿

**标题：** 做了一个 Mac 工具：按使用记录整理 iPhone 主屏幕，先预览再应用

整理 iPhone 主屏幕时，逐个拖动 App 很费时间。我把使用记录读取、排序预览、USB 写入和读回验证放进了一个本地工具 AppSort。

目前可以按打开次数、使用时长或最近使用排序，提供两行、完整页面、保留文件夹等预设；每页图标数量、小组件位置和页数预算都能调整，也能置顶、搜索、保存多份配置、导入和导出 CSV。

在线演示用虚构数据，可直接试用，不连接手机：https://asymptote637.github.io/iphone-appsort/demo/

实际手机需要 Mac 和 USB，已在一台 iPhone 17 / iOS 27.0 上完成交换、恢复和两行布局的读回验证。其他设备需要先测试。首次写入可能让仅在资源库中的 App 回到主屏幕，布局备份不能保证恢复这类系统状态，README 写明了这些边界。

源码和中文上手说明：https://github.com/asymptote637/iphone-appsort

欢迎反馈界面体验，或提供经过匿名化的兼容性结果。

## Short social post

AppSort: arrange an iPhone Home Screen from app opens, time or recency. Preview layouts, customize page density, keep folders/widgets, pin apps and save profiles. Local Mac + USB workflow, with read-back verification.

Try fictional data: https://asymptote637.github.io/iphone-appsort/demo/

Source and compatibility limits: https://github.com/asymptote637/iphone-appsort

## Follow-up topics

- How foreground activations differ from process launches and Screen Time pickups.
- Why phone read-back matters when a layout command exits successfully.
- How a page budget groups the smallest ranked tail while preserving inventory.
- How the usage helper handles macOS permission attribution without broad Terminal access.

Ship meaningful improvements and describe observable results. Compatibility reports should omit device IDs, pairing records, personal app inventories and raw usage databases.
