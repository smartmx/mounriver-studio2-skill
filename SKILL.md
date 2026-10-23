---
name: mounriver-studio2-skill
description: MRS2/MRS3 沁恒 MounRiver Studio 单片机工程操作：凡涉及 MRS2、MRS3、MounRiver Studio 2/3、.wvproj/.wvsln/.cproject/.template/.project/.launch、CH32/CH56x/CH57x/CH58x/CH59x、CH32V307、WCH-Link、EVT 例程、riscv-none-embed/riscv-wch-elf 工具链、OpenOCD 烧录、读保护、Eclipse CDT 单片机工程的发现/解析/编译/烧录/改配置，一律先读本 skill。
---

# MRS2/MRS3（MounRiver Studio 2/3）工程操作

WCH（南京沁恒）官方 IDE，用于 CH32 / CH56x / CH57x / CH58x / CH59x 等 RISC-V 与 ARM 内核 MCU。
**2 代与 3 代目录结构同构**：`resources\app\resources\win32\` 下的组件树完全一致——工具链与
前缀、make bundle、OpenOCD、芯片库全套通用；工程格式也是同一套 Eclipse CDT
（`.project`/`.cproject`）+ MRS 新增的空标记 `.wvproj`、solution 文本 `.wvsln`、下载配置
`.template`。**本文档两代通用**，个别差异（品牌代次判定、个别 DLL 位数）在 install-layout.md
与 flash-debug.md 标注。

**本 skill 以知识库为主**：references 是工程文件格式、flags 组装规则、烧录语义的权威文档。
解析、修改、编译、烧录由你（AI）**按文档直接操作工程文件与真实工具链**完成——gcc/make/OpenOCD
复用安装目录里的原版 exe；MounRiver 没有暴露任何可独立调用的解析引擎（IDE 内核是 Eclipse CDT
的 Java 框架）。`scripts/mrs2.py` 只是轻量辅助（安装定位（MRS2/MRS3）、工程发现、配置摘要、
芯片库查询、solution 解析、路径字符可构建性警告），**刻意不做编译/烧录执行器**：CDT 选项语义的
完整实现只有 MounRiver IDE 与 MRVC 插件（github.com/smartmx/MRVC），脚本复刻必然漂移。

## 环境约定

- 仅 Windows。编译 / 烧录 / 工具定位都需要 MounRiver Studio 2 或 3 的安装目录（下称
  `$MRS`；两代目录结构同构）。**路径来源按优先级**：`--mrs2 <安装根>` 参数（MRS2/MRS3
  通用，自动识别代次）→ 环境变量 `MRS2_HOME` / `MRS3_HOME` → 兜底探测 WCH 官方默认安装
  位置 `C:\MounRiver\MounRiver_Studio2`、`C:\MounRiver\MounRiver_Studio3`（MRS2 在前）。
  以上都不存在时：**提示"需要已安装 MounRiver Studio 2 或 3"并请用户提供安装路径**，
  不要再枚举其他目录；脚本也会以同样的提示报错。
  判定标志：`$MRS\resources\app\resources\win32\components\WCH\manifest.json` 存在；
  代次由 `resources\app\product.json` 的 `mrsVersion` 判定（见 install-layout.md「代次判定」）。
- 脚本：`python <skill目录>/scripts/mrs2.py <子命令> [--mrs2 <安装根>]`，Python 3.8+ 纯标准库。
- 完整目录结构、工具链解析、芯片库见 `references/install-layout.md`（定位工具前必读）。

## 快速决策表

| 任务 | 命令 |
|---|---|
| 找工程（EVT 树/任意目录递归，不需要安装目录） | `python scripts/mrs2.py find <目录>` |
| 解析一个工程（配置/源文件/排除/下载信息 + 路径字符可构建性警告） | `python scripts/mrs2.py show <工程目录> [--mrs2 <安装根>]` |
| 列出工具链（MRS2/MRS3 的 GCC8/12/15/ARM） | `python scripts/mrs2.py toolchain [--mrs2 <安装根>]` |
| 查芯片库（型号/地址/能力/chipID） | `python scripts/mrs2.py chips [--series CH32V307] [--mrs2 <安装根>]` |
| 解析 solution（不需要安装目录） | `python scripts/mrs2.py sln <文件.wvsln>` |
| **编译一个工程** | 读 `references/build.md`：优先复用 obj/ 已生成的 makefile 调 make；否则按配方组装 gcc 命令 |
| **烧录 / 调试 / 读保护** | 读 `references/flash-debug.md`：手写 OpenOCD cfg（WCH 双重地址语义是坑） |

`--mrs2 <安装根>` = MounRiver 安装目录（MRS2/MRS3 通用）；省略时按环境变量与
WCH 默认安装位置（`C:\MounRiver\MounRiver_Studio2` / `MounRiver_Studio3`）定位，
仍找不到才报错提示"请先安装并提供路径"。
加 `--json` 可让 `show`/`find`/`chips`/`toolchain`/`sln` 输出机器可读 JSON。

## 工程识别规则

- `<名字>.wvproj`：MRS 工程标记文件，**内容为空**（IDE 打开时重建）→ 其所在目录就是工程目录。
- `.project`：Eclipse 工程描述，MRS1/老 EVT 工程的兜底标记。
- `.wvsln`：solution（多工程编组）的纯文本文件。
- `.cproject`：构建配置（CDT XML），唯一的编译真相来源。
- `.template`：下载配置（Java properties 格式文本）：下载地址、hex 路径、擦除/校验/复位开关、芯片信息。
- `.launch`：调试配置（Eclipse XML）。
- 模板工程规范样例（可直接对照学习）：`assets/sample-ch32v307/`。

## 深入阅读（按需加载）

| 何时读 | 文件 |
|---|---|
| 解析或**修改** `.project`/`.cproject`/`.template`/`.wvsln`/`.launch` 之前 | `references/project-formats.md` |
| 定位工具链/OpenOCD/make/芯片库/GUI 工具之前 | `references/install-layout.md` |
| 编译（生成 makefile 或直接调用工具链）之前 | `references/build.md` |
| 烧录、调试、读保护、芯片操作之前 | `references/flash-debug.md` |
| 编译/烧录失败排错、路径异常、中文乱码 | `references/gotchas.md` |

## 铁律（违反会损坏工程或烧坏目标）

1. **改 `.cproject`/`.project` 前先备份原文件**；这两个文件必须保持 CDT/MRS 可打开——写 XML 时
   属性转义规则（`&`→`&amp;`、`<`→`&lt;`、属性内 `"`→`&quot;`）不可省，改完用 `show` 验证仍可解析。
2. **排除编译 = 修改 `.cproject` 的 `sourceEntries`**（两种风格见 project-formats.md），不是删文件。
3. `obj/`（配置名对应目录）是构建输出：不要往里放源文件，不要手工编辑其内容。
4. 写 `.template`、OpenOCD cfg、makefile 一律用**系统 ANSI 代码页**（zh-CN Windows 即 GBK），
   不是 UTF-8——OpenOCD 的 Jim Tcl 和 make 都按系统代码页读这些文件；cfg/脚本里的路径用正斜杠
   （Jim Tcl 会吞反斜杠：`<盘符>:\x\y` 会变成 `<盘符>:xy`）。
5. 下载地址优先取 `.template` 的 `Address=`；缺失时用 `chips` 命令或推断规则（CH5x 无线系列
   `0x00000000`，CH32x/CH564/CH64x `0x08000000`）。非法地址直接报错，不要猜。
6. 双核工程（CH32H417 V3F/V5F）用 `wch-dual-core.cfg`，全片擦除要擦 2 个 bank（core1 bank 在
   `0x00005000`）。
7. WCH 的 OpenOCD 里下载地址要**传两次**：`wlink_set_address`（bank 基址，init 时采样）和
   `program <file> <offset>` 的偏移；hex 自身链接地址（CH5x 是 0x00000000）参与偏移换算，
   详见 flash-debug.md——直接 `program hex 0x08000000` 会得到 "no flash bank found" 且什么都不写。

## 修改配置的最短路径

编译开关/包含路径/宏定义/链接脚本都存在 `.cproject` 里，**选项以 `superClass` 后缀为键**，例如
`option.optimization.level`（枚举：`size`→`-Os`）、`option.c.compiler.include.paths`（`-I` 列表）、
`option.c.linker.scriptfile`（`-T`）。改值前先读 `references/project-formats.md` 的 superClass
对照表和 flags 映射（build.md），用 `show` 确认改动了预期选项。
