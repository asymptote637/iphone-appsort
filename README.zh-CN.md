# AppSort：按使用频率整理 iPhone 主屏幕

把经常打开的 App 排到前面，省去逐个拖动图标的时间。
次数、时长、最近使用三种排序，多种预设与自定义布局，先预览、再写入并读回确认。
适合有 Mac 的 iPhone 用户：本地处理、USB 连接、无需越狱。

[![CI](https://github.com/asymptote637/iphone-appsort/actions/workflows/ci.yml/badge.svg)](https://github.com/asymptote637/iphone-appsort/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/asymptote637/iphone-appsort)](https://github.com/asymptote637/iphone-appsort/releases/latest)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)

**[在线体验 →](https://asymptote637.github.io/iphone-appsort/demo/)** · [下载版本包](https://github.com/asymptote637/iphone-appsort/releases/latest) · [English](README.md) · [讨论区](https://github.com/asymptote637/iphone-appsort/discussions)

![使用虚构次数生成的 AppSort 两行排列预览](docs/assets/demo.jpg)

*在线演示和截图使用虚构数据，不连接手机。*

> **真机使用前请了解：** 首次写入可能让原本仅在 App 资源库中的 App 回到主屏幕；布局备份不能保证恢复这种状态或隐藏页面。当前实机验证覆盖一台 **iPhone 17 / iOS 27.0（24A437）**，其他设备与系统需要先做交换和恢复测试。

## 目录

- [无需手机先体验](#无需手机先体验)
- [功能](#功能)
- [连接自己的 iPhone](#连接自己的-iphone)
- [实测与边界](#实测与边界)
- [同类方案与来源](#同类方案与来源)
- [参与贡献](#参与贡献)

## 无需手机先体验

直接打开 **[在线演示](https://asymptote637.github.io/iphone-appsort/demo/)**，或用 Python 3.11+ 启动真实界面的示例模式：

```bash
git clone https://github.com/asymptote637/iphone-appsort.git
cd iphone-appsort
python3 -m appsort --demo serve --port 8767
```

打开 `http://127.0.0.1:8767/`。不需要安装第三方依赖、连接 USB 或授权私人记录。可以试用四种预设、次数 / 时长 / 最近使用、自定义图标数、搜索、置顶、保存配置和导出 CSV；示例模式禁用手机读写。

演示在两个周期中使用固定的虚构数值，切换 7 / 30 天用于体验流程，不代表真实统计。桌面界面目前以中文为主，在线演示的主要控件提供英文展示。退出时关闭终端或按 Ctrl+C。

## 功能

- **三种排序：** 近 7 / 30 天的打开或切回前台次数、累计使用时长、最后一次前台记录；缺少记录的 App 排在后面，同分时保留相对顺序。
- **四种可修改预设：** 顶部两行、完整页面、保留文件夹、最近使用，任何预设都可以继续调整。
- **自定义密度与页数：** 每页 1–24 个图标，总页面预算 1–15 页，包含小组件页、不含 Dock；必要时只合并排名末尾的最少数量 App。无法安全合并既有文件夹时会停止并提示调整。
- **文件夹与小组件：** 展开文件夹或保留并排序，按原位置保留小组件或将完整叠放独立放在第一页；Dock 始终固定。
- **置顶、搜索、配置保存：** 置顶优先于自动排名，按名称或 bundle ID 查找 App，在本机保存多份有名字的设置。
- **导入与导出：** CSV 支持打开次数、可选时长和带时区的最近使用时间；可导出完整使用表 CSV 或排序记录 JSON。
- **备份与读回核验：** 写入前保存原始 plist，读回区分成功、被忽略、部分应用和未确认；系统未接受布局时不会报成功。
- **本地处理：** 私人 state 不进入 Git 或版本包，桌面服务只监听 127.0.0.1，在线演示仅含示例数据。
- **CLI / Codex：** 命令行与界面共享校验逻辑，附带可选 [Codex skill](codex-skill/iphone-appsort/SKILL.md)。

### 先选预设，再按需调整

| 预设 | 排序 | 每页图标 | 文件夹 | 小组件 |
|---|---|---:|---|---|
| 顶部两行 | 次数 | 8 | 展开 | 独立第一页 |
| 完整页面 | 次数 | 24 | 展开 | 原位置 |
| 保留文件夹 | 时长 | 16 | 保留 | 原位置 |
| 最近使用 | 最近一次记录 | 12 | 展开 | 独立第一页 |

“顶部两行”适用于小组件独立后的 App 页。选择保留小组件原位时，小组件面积仍占用页面空间，工具会检查两者的总面积。保留文件夹时，次数和时长使用内部 App 之和，最近使用取内部最新的一次记录。

在“保存与加载本地配置”中保存设置。同名保存会更新配置，加载后需要生成新预览才能应用。配置仅保存为私人 `state/profiles.json`，不自动定时写入手机；在线演示只在浏览器保存虚构配置。

CSV 表头为 `bundle_id,opens,seconds,last_open`，后两列可省略。最近使用需要含时区的 ISO 时间，如 `2026-01-01T08:00:00+08:00`。参见 [示例 CSV](examples/counts.csv)。

## 连接自己的 iPhone

| 需求 | 条件 |
|---|---|
| 手机整理 | Mac、Python 3.11+、USB 连接、手机解锁并信任 Mac |
| 使用次数 | 同一 Apple ID，屏幕使用时间开启“在设备之间共享”，有同步记录 |
| 复制助手 | Xcode Command Line Tools / swiftc，给编译后的助手完全磁盘访问权限 |
| 可选 cfgutil | 安装 **Mac 版** Apple Configurator；含小组件时禁用这一路径 |
| 示例与测试 | Python 3.11+，无需手机与 USB 依赖 |

```bash
git clone https://github.com/asymptote637/iphone-appsort.git
cd iphone-appsort
bin/setup
bin/appsort serve
```

也可以下载源码 ZIP，双击 **Setup AppSort.command**，再双击 **Start AppSort.command**。缺少 Python 和 Xcode 命令行工具时先安装它们。这是 Mac / USB 工具，无需 Docker 部署。

在“系统设置 → 隐私与安全性 → 完全磁盘访问权限”添加 `bin/appsort-usage-helper`。授权前可查看 [Swift 源码](helper/screentime-copy.swift)。完全磁盘访问本身是广泛权限；该助手的实现只复制同步的 App.InFocus 前台记录和设备清单，不修改权限、不上传。

操作顺序：

1. 选择已信任的 USB iPhone，读取布局。
2. 读取同步记录，确认对应的设备流，统计所选周期；旧手机也可能保留在清单中。
3. 选预设或自定义规则，生成预览，检查小组件、置顶、页数和末尾合并文件夹。
4. 做交换与恢复测试：真实交换两个图标，读回后恢复并再次核验。
5. 在当前设备 / 系统 / 接口测试通过后，应用已查看的预览。

首次同步可能要数小时，记录也可能落后于手机实时活动；界面显示实际截止时间。这里的次数包含切回前台，不等于进程冷启动或拿起手机次数。

读取手机与对应使用记录后，命令行也可指定规则：

```bash
bin/appsort propose --metric recent --days 7 --capacity 12 --page-limit 10 --folders preserve --widgets separate
bin/appsort propose --metric opens --capacity 24 --widgets keep --pin com.example.app
```

置顶标识请换成自己手机上实际存在的 App。命令行帮助为 `bin/appsort --help`。`test`、`apply`、`restore` 默认询问具体写入确认；`--yes` 表示已经查看并授权本次操作。

## 实测与边界

| 检查 | 证据 |
|---|---|
| 软件测试 | 62 项单元与 HTTP 测试，以及 288 种演示 / 桌面配置对比；[CI](https://github.com/asymptote637/iphone-appsort/actions) 使用模拟设备运行单元与 HTTP 集成测试 |
| 实机 | 一台 iPhone 17，iOS 27.0，构建号 24A437 |
| 原始布局接口 | 已实际交换、恢复和应用排序，独立手机读回得到一致结果 |
| 最终实测布局 | 小组件独立页 + 14 个各有 8 个图标的 App 页，Dock 固定，清单完整 |
| 使用记录 | 真实同步 Biome 事件已解析，次数与时长分开统计 |
| cfgutil | 已实现，当前版本尚未实机验证，含小组件时禁止使用 |
| 其他版本 | 未验证；示例或 CI 成功不能证明它们接受手机写入 |

更多说明见 [验证记录](docs/validation.md)。不提供虚构的性能数据或所有版本兼容承诺。

这是 Mac 工具，可配合浏览器界面和 Codex skill 使用，不会在 iPhone 上安装启动器，也不会持续自动搬动图标。

布局备份不是完整手机备份。原始接口不能保证恢复 App 资源库状态、隐藏页面等设置。首次写入发现额外图标时，工具会报告清单变化并停止旧预览；恢复“仅资源库”状态可能需要在手机上手动处理。

## 同类方案与来源

| 方案 | 文档所述侧重 | AppSort 的侧重 |
|---|---|---|
| 手机手动排列 | 在手机上拖图标 | 基于使用记录生成可预览排序 |
| [Appabetical](https://github.com/Avangelista/Appabetical) | 按字母 / 颜色；README 限定 iOS 14–16.1.2 | 使用次数、Mac 预览、逐设备验证 |
| [homescreen-organizer](https://github.com/justinleveck/homescreen-organizer) | Mac 编辑器、使用记录和 Claude Code skill | 三种指标、多预设、自定义与配置保存、写入验证门槛 |
| [iphone-layout-tool](https://github.com/tmad4000/iphone-layout-tool) | cfgutil 转换与写入 | 使用记录、预览、备份与读回分类整合 |

本项目沿用并改进上游研究。Biome 解码器与 Swift 助手保留 MIT 来源署名，项目依赖、许可和感谢见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 参与贡献

从 [贡献说明](CONTRIBUTING.md)、[good first issue](https://github.com/asymptote637/iphone-appsort/labels/good%20first%20issue) 或 [讨论区](https://github.com/asymptote637/iphone-appsort/discussions) 开始。欢迎界面翻译、同步诊断、键盘导航和经过匿名化的兼容性反馈。

请不要提交手机号、设备标识、配对记录、原始使用数据库、私人截图或 state。发现安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

另附 [推广文案包](docs/launch-kit.md)，包含中英文社区发帖草稿与演示操作顺序。

如果它帮你省去了整理时间，欢迎 Star，或在相关问题下分享完整使用经验，让有同样需要的人找到它。

**协议：** [GPL-3.0-or-later](LICENSE)。本项目与 Apple 无关联。
