# MRS2/MRS3 工程坑清单（排错时读）

按"现象 → 根因 → 处置"组织。这些坑全部来自对 MRS2 真实工程（EVT 树、SDK 模板、MRS1 遗留）
的处理经验。

## 编码与文件读写

- **双编码现实**：`.project`/`.cproject`/`.launch` 声明 UTF-8，但含中文工程名的 `.template`、
  `.wvsln`、makefile 可能是 ANSI/GBK。读文件：先 UTF-8 试解码，失败回退 GBK（`cp936`）。
  写 `.template`/cfg/makefile：Windows 一律系统 ANSI（`locale.getpreferredencoding(False)`，
  zh-CN 即 GBK/`mbcs`）；Linux/macOS 没有 ANSI 代码页，**按文件原编码写回**（新建 cfg 用
  UTF-8）。UTF-8 写入 Windows 上中文路径的 cfg 会让 OpenOCD 的 Jim Tcl 打不开文件。
- XML 转义：写回 `.cproject`/`.project` 时 `&`→`&amp;`（先做）、`<`→`&lt;`、属性内 `"`→`&quot;`。
  列表值里的宏形如 `&quot;${workspace_loc:...}&quot;`——**路径类**字段（include 路径、库搜索
  路径、链接脚本）取值剥引号、写回补引号；但 `libraries` / `defined_symbols` 进 MRS2 模型是
  **原样**的（读侧 `EPMacroStrResolve` 只剥路径类），库名 `m` 不要写成 `"m"`——程序化复制
  列表值**逐属性原样克隆**最稳（见 project-formats.md「值写法保真」）。
- **空元素形态保真**：MRS2 写的 `.project` 里空元素两种写法并存——`<comment/>` 自闭合，
  `<projects>` / `<arguments>` 却是跨行开闭对（另有极少数 ` />` 斜杠前带空格的变体）。解析
  → 写回要记住**每个元素**的源形态，别统一成 `<x/>`：真实 EVT 普查 1,485/2,687 个 `.project` 含开闭
  对写法，一次无关写入就会把文件里每一处都改写（1,067 → 1,022 字节的纯形态 diff）。
- `.template` 是行式 properties：键值 `K=V`、`#`/`!` 开头是注释、空行分节、`\n` 是字面转义
  （Description 里常见）。重写时保留原有注释与空行，CRLF 行尾。

## 路径与链接资源

- **Windows 路径比较必须大小写折叠**（NTFS 不敏感）：判断文件是否在目录内、工程是否重复时
  先 `lower()`。漏折叠会把合法路径误判为外部路径。
- `${workspace_loc:/OtherProj/X}` 的 Eclipse 语义是"工作区根下的其他工程"，但 MRS2 实际按
  工程根解析——多工程 solution 里这样的 include 会指到不存在的目录，然后被静默丢弃（构建
  不报错但头文件找不到）。排查 include 丢失时先查这个。
- include 目录不存在会被**静默丢弃**（MRS 同款）：-I 列表比 .cproject 短一条不一定是 bug。
- `PARENT-N-PROJECT_LOC` 链接（EVT 共享 PUB 目录的方式）在发布包里常残留打包机器的绝对路径。
  修复：从工程目录逐级向上找第一个包含尾段的祖先目录，改写为 `PARENT-N-PROJECT_LOC/尾段`。
- **EVT 例程与同级 `SRC/` 配套**：`EXAM/<例程>` 的 `.project` 用
  `PARENT-1-PROJECT_LOC/SRC/...` 链接同级 `EXAM/SRC/`（`Ld` / `RVMSIS` / `Startup` /
  `StdPeriphDriver`；`CH58x_common.h` 就在 `SRC/StdPeriphDriver/inc/`）。**单独拷走例程目录 =
  链接全部失效**，编译报缺 `CH58x_common.h` 等头文件——拷贝/移动例程必须连同同级 `SRC/`
  一起（保持 `<例程>/ + SRC/` 布局），或按上面规则改写链接。
- 符号链接/junction 循环：递归扫描源文件或工程发现时带深度上限或已访问集合，否则自指
  junction 会栈溢出。
- Windows 保留设备名（`CON`/`NUL`/`COM1`/`LPT1`…）与尾部点/空格的目录名会让 mkdir 产生
  裸 Win32 错误；尾点/尾空格会被系统剥掉，导致目录名与请求名不一致。

## sourceEntries / 排除语义

- 根 entry `excluding` 里的**裸目录名是双含义**：既是排除列表成员又是"该目录有自己的命名
  entry"的防双扫标记。扫描实现必须同时处理两种，否则要么重复编译要么漏编译。
- excluding token 匹配：含 `/` 的 token 按**前缀**匹配（工程根相对）；裸 token 只匹配直接
  子项。不要用"后缀匹配"（`endsWith('/'+tok)`）——`Ld/Link.ld` 会误伤任意深度的
  `User/Ld/Link.ld`。
- 对"有自己的命名 entry 的顶层目录"做排除时，只往根 entry 加裸名是**无效操作**（扫描器会把
  该目录从命名 entry 再加回来）。必须改写/删除那个命名 entry 的 excluding 列表。
- CH58x 的 `StdPeriphDriver` entry 几乎必然带着一串 `CH59x_*.c` 级别的文件排除（外设裁剪），
  这是预期行为；链接报 undefined reference 先查这里。

## 构建域

- makefile 域字符能力**分层判定**（逐字符实测矩阵见 build.md「路径字符与 recipe 执行 shell」）：
  规则词层 `;`（行内 recipe）`#`（注释）不可转义，`%` 在非模式规则词中是字面量，`[` 触发
  glob（匹配不到则保持字面）；shell 层（无引号展开）`& ( ) '` 拆命令破引号、`[ ]` glob 到
  错误对象。**工程根本身含 `( ) ; % # & @ ! , ~ '` 实测全部可编译**（根字符只进相对 prereq
  与引号旗标参数）——勿按旧结论把带括号的 EVT 发布目录（`CH5xxEVT_Vx.y_(YYYYMMDD)` 型）
  误判为非法路径。唯一全通道拒绝的是**反引号**（sh 双引号内仍命令替换）。`$` 需 `$$`（只转义
  用户数据，勿碰 make 自动变量）；空格需引号或显式规则。**树内源文件名仍要检**（`main(1).c`
  这类下载解压产物不在支持范围）。
- 链接目录的宿主判定按**解析后的绝对路径**（含工程根与其祖先）：根带 `;` `#` 时该工程下
  **每个链接目录**都不可构建（链接文件规则的 prereq 是绝对路径，字符进规则词）。无链接的
  同名工程不受影响。
- MRS2 自身的 `#` 误改写 bug：根路径含 `#` 时其生成的 makefile 把 `#` 写成 `%`（错误路径）
  照样失败——诊断含 `#` 的链接工程先看 obj/ 里规则词路径是否被改过。
- cmd.exe 批处理层（.cmd 调 make）：`%` 写 `%%`；`!` 需 `setlocal DisableDelayedExpansion`
  兜底（父环境 AutoRun 或 `/v:on` 开延迟展开会吞 `!`）；.cmd 与 makefile 同按系统 ANSI 码页
  解析。看实际命令用 `make -n -B all` 干跑（recipe 被 `@` 静默时干跑是唯一全量暴露手段）。
- make 自动变量（`$@` `$<` `$^`）**不能**做 `$`→`$$` 的全串转义——只转义用户数据（路径、宏）
  里的 `$`。全串转义会把 `-adhlns="$@.lst"` 变成 `$$@`，汇编清单静默失效。
- 同名不同目录的 `.c`（`SRCA/foo.c` 与 `SRCB/foo.c`）在 CDT 目标布局下会产生同名 .o 冲突；
  自己实现构建时按相对路径命名 .o 天然规避。
- 显示名带空格的工程（导入工程常见）会让 `${ProjName}.elf` 目标在 makefile 里裂成两个目标
  ——MRS2 自己也有此问题，报错时先查显示名。
- 配置名（cconfiguration 的 name）决定构建目录；罕见工程配置名不是 `obj`，别硬编码。

## Solution / 多工程

- `.wvsln` 成员行相对**文件所在目录**解析：自写时相对成员必须以 `..\` 开头。
- `BuildOrder=` 按工程**显示名**（不是目录名）排序；改写 BuildOrder 时注意幂等——先判断
  是否已有该行再决定插入位置，否则每次编辑都会累积重复行。
- 成员里的陈旧绝对路径/重复行要容忍：去重（大小写折叠）、标记不存在、不要因为坏行放弃整个文件。
- 工程改名后 solution 里的旧名成为死条目；重命名级联清单见 project-formats.md。

## 芯片与烧录域

- 双核（CH32H417）：cfg 用 `wch-dual-core.cfg`；eraseAll 要擦 2 个 bank（core1 在
  0x00005000）；用户自定义 cfg 时 bank 数未知，按 1 处理并让单核流程兜底。
- hex 的"下载地址"与"链接地址"是两回事（详见 flash-debug.md 的双重地址语义）；bin 没有
  内部地址，offset = 下载地址。
- Intel HEX 只需处理 type 00/01/04；`<<16` 在 upper ≥ 0x8000 时有符号溢出，用 `* 0x10000`。
- 工具链代际与 `-march` 语法：GCC8 `rv32imacxw`，GCC12/15 `rv32imac_xw`（及 `_zba_zbb_zbc_zbs`
  `_zmmul`）。切换代际要同步 `.cproject` 的 `option.command.prefix`。
- flash.json 的 `support_*` 能力开关为 false 时，对应操作（如 debugInterfaceMode）在该芯片
  不可用，不要盲目下发。

## 跨平台（Linux / macOS）

- **MRS2 在非 Windows 只有纯工具链包**：`MRS_Toolchain_*` 顶层只有 `Toolchain/` + `OpenOCD/`，
  没有 IDE、没有 `SDK/default`、没有自带 make。别在 Linux/mac 找 `MounRiver Studio 2.exe`
  或模板 zip；完整 IDE 与芯片库只有 **MRS3**（Linux tar.xz/.deb、macOS arm64 `.app`）。
- **别按文件名判包**：`MRS_Toolchain_Linux_X64_V300.tar.xz` 实际是 MRS3 完整 IDE；
  `..._V240.tar.xz` 才是纯工具链。看解包内容有没有 `resources/app`。
- **在 Windows 上解包 Linux/mac 包会丢符号链接**（tar/zip 权限），GCC 插件 `.so` 缺链接后
  工具链不可用；应在目标平台解包，或用保留符号链接的工具（WSL2 的 tar、7-Zip 需注意）。
- **架构**：macOS MRS3 IDE 是 **arm64 专用**；V2.4 mac 工具链包是**混合架构**（GCC8 与 ARM =
  x86_64，GCC12/15 = arm64）。Intel Mac 只能用 V2.4 纯工具链包的 GCC8/ARM（MRS3 IDE 跑不了）；
  Apple Silicon 优先 MRS3 arm64 IDE。症状：`Bad CPU type in executable`（mac）、
  `Exec format error`（Linux 拷错包）。
- **可执行位**：从 zip/Windows 拷贝会丢 `+x`；gcc/make/openocd 报 `Permission denied` 时
  `chmod +x`。工具链清单里是裸名，POSIX 不要补 `.exe`。
- **PATH 与大小写**：PATH 分隔符 `:`（Windows `;`）；Linux/mac 文件系统区分大小写，
  `.cproject` 的 `excluding` token、`#include`、链接资源名必须与磁盘大小写一致
  （Windows 上做大小写折叠比较，POSIX 不能照搬）。
- **Windows 绝对路径**：`.cproject`/`.template`/`.launch` 里的 `C:\...`、反斜杠在 POSIX
  不会解析；改成 `${workspace_loc}`、相对路径或 POSIX 绝对路径。`.wvsln` 成员行同理。
- **编码**：POSIX 没有 ANSI 代码页；从 Windows 拷来的 GBK `.template`/`.wvsln`/makefile 仍按
  GBK 读（先 UTF-8 试解码、失败回退），写回按原编码；新建文件用 UTF-8。不要用 locale
  编码覆写 GBK 文件。
- **GUI 工具缺席**：WCH-LinkUtility / WCHISPTool / WCHTouchKeyTool / WCHGUIDesigner /
  WCHToolKit / HexBinStudio / COMTransmit 只在 Windows 安装里；Linux/mac 按组件缺失降级，
  不要拼不存在的 `.exe` 路径。
- **纯工具链包无 make/SDK**：构建用系统 GNU make；`chips` 不可用；新建工程模板要用 IDE 的
  `SDK/default`（或 Windows 安装）。
- **烧录**：Linux 需 udev 规则（`50-wch.rules` / `60-openocd.rules`，`plugdev`）；macOS 未实测；
  wlink 底层库三平台同名（`libmcuupdate.so`/`.dylib` vs Windows `McuCompilerDll.dll`），
  POSIX 走进程内 FFI 但**未经真机实测**。详见 flash-debug.md「平台差异」与「WCH-Link 底层操作」。
- **WSL2**：构建链路可全程在 WSL2 跑；USB 烧录用 usbipd-win 直通 WCH-Link。

## 已知失败模式（现象速查）

| 现象 | 第一排查点 |
|---|---|
| 构建成功但 .lst/栈分析产物没生成 | `$@` 被过度转义（makefile 域）或分析 dump 头解析没截断 `(..., funcid=N)` |
| 烧录"成功"但芯片没反应 | hex 双重地址换算错；或擦的是 bank 0、代码在 bank 1（双核） |
| 排除文件后仍被编译 | 根 entry 裸名标记语义 / 命名 entry 未改写 |
| 打开 MRS2/MRS3 后工程属性空白/报错 | .cproject XML 转义或结构被破坏——用备份恢复后按 superClass 表重新改 |
| 中文日志乱码 | 控制台按 GBK 解码了 UTF-8 输出（或反之）；工具链输出按 ANSI 处理 |
| 正规 Windows 路径被构建拒绝 | 分层判定错位：工程根 `( ) ; % # & !` 本身合法；真正拒绝的只有链接路径的 `;` `#`、USER_OBJS 的 `& ( ) ' [ ] ; #`、一切反引号（build.md 实测矩阵） |
| `C:` 盘符路径跑到别处 | `path.resolve("C:")` 解析到该盘当前目录；盘符根必须写成 `C:\` |
| Linux/mac 找不到 MRS2 IDE / `SDK/default` | 非 Windows 的 MRS2 代官方包是纯工具链（无 IDE/无 SDK/无 make）；完整 IDE 用 MRS3 |
| `Bad CPU type in executable` / `Exec format error` | 架构不符：Intel Mac 装 arm64 MRS3、V2.4 mac 包的 GCC12/15 是 arm64、或 Linux 包拷到 mac；见 install-layout.md「架构门禁」 |
| `Permission denied` 执行 gcc/make/openocd | 拷贝丢了可执行位；`chmod +x` |
| POSIX 下 `Permission denied` 访问 WCH-Link USB | udev 规则未装或用户不在 `plugdev`；见 flash-debug.md「平台差异」 |
| 改 `.cproject` 后在 Linux/mac 编译丢文件 | POSIX 区分大小写，`excluding`/`#include` 大小写与磁盘不一致（Windows 折叠比较掩盖了问题） |
| EVT 例程编译报缺 `CH58x_common.h` 等头 | 例程被单独拷出、脱离了同级 `EXAM/SRC/`（`PARENT-1-PROJECT_LOC/SRC/...` 链接断）；连同 `SRC/` 一起拷或改写链接 |
