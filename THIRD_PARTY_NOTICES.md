# 来源与许可

AppSort 的 Biome 前台记录解码方法与 Swift 复制助手改编自 Justin Leveck 的 [homescreen-organizer](https://github.com/justinleveck/homescreen-organizer)，来源固定在 commit `4da2109a46fa0fd5deeace947d345e475f19c68c`。许可原文见 `licenses/homescreen-organizer-MIT.txt`。

写入协议参考 [tmad4000/iphone-layout-tool](https://github.com/tmad4000/iphone-layout-tool) 描述的 Apple Configurator `cfgutil set-icon-layout` 用法。本工具未复制该仓库的代码。

运行依赖：
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)：USB 读取，GPL-3.0。通过项目私有虚拟环境安装，保留其发行包许可。
- [ccl-segb](https://github.com/cclgroupltd/ccl-segb)：SEGB 文件解析，MIT。通过原仓库安装，保留其发行包许可。

本工具源码按 GPL-3.0-or-later 发布，以兼容运行依赖。Apple Configurator 由 Apple 发布并单独安装。
