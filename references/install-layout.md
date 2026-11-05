# MRS2/MRS3 安装目录结构与工具链解析

所有工具组件都在 `<安装根>/resources/app/resources/<平台层>/` 下（MounRiver 本体是 VSCode
内核套壳，这一层是它的资源目录）。平台层目录名：Windows `win32`、Linux `linux`、macOS `darwin`
（macOS 在 `.app/Contents/Resources/app/resources/darwin`）。**MRS2 与 MRS3 的 IDE 目录结构
同构**——下面整棵树对两代、三平台都成立，工具链前缀、make、OpenOCD、芯片库全套通用；区分点
只有品牌/版本判定、POSIX 组件缺席与个别组件位数（见「平台形态」「代次判定」与树内标注）。
`<安装根>` 指定位到的 MounRiver Studio 2/3 安装目录或纯工具链根（来源见下方「安装路径的来源」）。

## 平台形态（先看这张表）

| 平台 | MRS2（V2.x） | MRS3（V3.x） |
|---|---|---|
| Windows | 完整 IDE | 完整 IDE |
| Linux | **纯工具链包**（`MRS_Toolchain_Linux_X64_V240` 型：顶层 `Toolchain/` + `OpenOCD/`） | **完整 IDE**（tar.xz 解包，或 .deb 实装 `/usr/share/MRS3/MRS-linux-x64`） |
| macOS | **纯工具链包**（`MRS_Toolchain_MAC_V240` 型） | **完整 IDE**（`MounRiver Studio 3.app`，arm64 专用） |

- 非 Windows 的 MRS2 代官方包**没有 IDE、没有 SDK、没有自带 make**——`Toolchain/` + `OpenOCD/`
  就是全部。工程仍可用它编译，但芯片库查询、模板新建工程要用 MRS3 IDE（或 Windows 安装）。
- **命名陷阱**：`MRS_Toolchain_Linux_X64_V300.tar.xz` 虽然名字叫 Toolchain，实际是 **MRS3 3.0
  完整 IDE**（解包为 `MRS-linux-x64/`，含 `resources/app`）；`..._V240.tar.xz` 才是纯工具链。
  **按内容判（有无 `resources/app`），不要按文件名判**。
- Linux 另有 UOS / Kylin / Deepin 等国产系统变体；布局未实测，按 Linux 平台层对待。Arch 系有
  社区 AUR 包 `mounriverstudio-bin`，安装前缀/布局以实际包为准，未纳入惯例探测。
- 一个完整 IDE 的 MRS3 Linux/macOS 包仍带 `extensions/mrs-team.mrs-vscode`（行为逆向来源与
  Windows 同款）。

## 目录总览（以 Windows 平台层为例）

> Linux/macOS 把路径里的 `win32` 换成 `linux` / `darwin`，并把所有 `.exe` 去掉；组件集合差异见
> 下一节。macOS 的顶层在 `.app/Contents/` 下。

```
<安装根>\                                  ← 用户提供的 MounRiver Studio 2/3 安装根
└── resources\app\resources\win32\         ← 资源层（示例：Windows 层；两代同构）
    ├── components\WCH\
    │   ├── manifest.json                   ← 安装完整性标志文件（探测用；两代通用，不区分代次）
    │   ├── Toolchain\
    │   │   ├── sub_manifest.json           ← 工具链清单（唯一可信来源，见下）
    │   │   ├── RISC-V Embedded GCC\        ← GCC8 (v8.2)，prefix riscv-none-embed-
    │   │   ├── RISC-V Embedded GCC12\      ← GCC12 (v12.2)，prefix riscv-wch-elf-
    │   │   ├── RISC-V Embedded GCC15\      ← GCC15，prefix riscv32-wch-elf-（注意是 riscv32-）
    │   │   └── arm-none-eabi-gcc\          ← ARM 工具链
    │   ├── OpenOCD\
    │   │   └── OpenOCD\bin\
    │   │       ├── openocd.exe             ← 两代均 32 位，版本同为 0.11.0+dev-snapshot
    │   │       ├── wch-riscv.cfg           ← 默认 RISC-V 板配置
    │   │       ├── wch-dual-core.cfg       ← CH32H417 双核 (V3F/V5F)
    │   │       ├── wch-arm.cfg / wch32f103.cfg / openocd_jlink.cfg / openocd_gdlink_riscv.cfg
    │   │       ├── McuCompilerDll.dll      ← 32 位拷贝（匹配 32 位 openocd 宿主；wlink 桥别用这份）
    │   │       └── [MRS3 额外] IoCHubDLL.dll / MRSRemoteAssistant.*  ← 远程调试助手，命令行流程用不到
    │   ├── SDK\default\
    │   │   ├── ARM\<系列>\...              ← ARM 模板
    │   │   └── RISC-V\<系列>\<RTOS>\
    │   │       ├── <芯片型号>.zip          ← 每个芯片型号一个完整可编译模板工程
    │   │       ├── <系列>-flash.json       ← 下载地址/chipID/能力开关（系列级）
    │   │       ├── <系列>-targetProcessor.json ← ISA/ABI 默认值（系列级）
    │   │       └── <系列>xx.svd            ← 外设寄存器视图
    │   └── Others\
    │       ├── SWDTool\                    ← WCH-LinkUtility（调试器配置/固件升级 GUI）
    │       ├── CommunicationLib\default\   ← McuCompilerDll.dll + load.wcfg（wlink 桥用；
    │       │                                  位数随代次：MRS2=32 位、MRS3=64 位）
    │       ├── IQMath\                     ← WCH IQmath 库 (-lIQmath_RV32)
    │       ├── WCHISPTool\default\WchIspStudio.exe
    │       ├── WCHTouchKeyTool\default\WCHTouchKeyTool.exe
    │       ├── WCHGUIDesigner\default\WCHGUIDesigner.exe
    │       ├── [MRS3 额外] WCHToolKit\default\WCHToolKit.exe  ← "WCH 工具集"（Electron，工具统一入口）
    │       ├── [MRS3 额外] WCHAgent\default\opencode.exe      ← "WCH Agent"（内置助手组件；MRS2 两者皆无）
    │       └── Firmware_Link\  WCHLinkEJtagUpdTool\
    └── others\
        ├── Build_Tools\Make\bin\make.exe   ← 还有 sh.exe rm.exe mkdir.exe echo.exe busybox.exe
        ├── COMTransmit\COMTransmit.exe     ← 串口调试
        ├── HexBinStudio\HexBinStudio.exe
        └── AssociateTool\  DemoLib\  ExTool\ KeilConvert\ LinkDrv\
```

### Linux / macOS 平台层差异

- **可执行文件没有 `.exe` 后缀**：`riscv-wch-elf-gcc`、`openocd`、`make`。`sub_manifest.json`
  里的名字本来就是裸名；Windows 靠 CreateProcess/PATHEXT 补 `.exe`，POSIX 直接用裸名。
- `components/WCH/Others/` 只有 **`CommunicationLib`、`Firmware_Link`、`IQMath`、`WCHAgent`**
  ——没有 `SWDTool`（WCH-LinkUtility）、`WCHISPTool`、`WCHTouchKeyTool`、`WCHGUIDesigner`、
  `WCHToolKit`（Windows MRS3 专属）。
- 平台层 `others/` 只有 **`Build_Tools`、`DemoLib`**（没有 COMTransmit / HexBinStudio /
  AssociateTool / ExTool / KeilConvert / LinkDrv）。菜单项按组件缺失降级隐藏。
- **OpenOCD `bin/` 形态不同**：Windows 带一堆随包 DLL（`libhidapi-0.dll`、`libjaylink-0.dll`、
  `libusb*.dll`、`McuCompilerDll.dll`、`libstdc++-6.dll`…）；Linux/macOS 只有 `openocd` 本体
  + cfg，依赖由系统或包内其他目录提供。
- `Others/CommunicationLib/default/` 在 POSIX 是**实库**：Linux 放 `libmcuupdate.so` +
  hidapi/jaylink/usb/ncurses 依赖（同目录还有 `50-wch.rules` / `60-openocd.rules`）；macOS 放
  `libmcuupdate.dylib` + hidapi/usb dylib——这是 wlink 底层操作的原生库（三平台同名导出，
  见 flash-debug.md「WCH-Link 底层操作」）。纯工具链包没有 `Others/`。
- IDE 自带 make：`others/Build_Tools/Make/bin/make`（Linux x86-64、macOS arm64，与 IDE 同架构）；
  **纯工具链包没有 make**，构建用系统 PATH 里的 GNU make。
- OpenOCD 配置集随包不同（实测）：Linux MRS3 有 `wch-riscv.cfg` / `wch-dual-core.cfg` /
  `wch-arm.cfg`；macOS MRS3 另有 `openocd_jlink.cfg`；V2.4 纯工具链的 Linux 版只有前三个，
  macOS 版多 `openocd_jlink.cfg`。`wch32f103.cfg` / `openocd_gdlink_riscv.cfg` 在部分包中缺席。
- Linux IDE 的 WCH/OpenOCD 目录还带 `MRSRemoteAssistant.chipID`（远程调试，CLI 流程用不到）。

## 纯工具链包布局（Linux / macOS 的 MRS2 代）

```
<解包根>/
├── Toolchain/
│   ├── sub_manifest.json
│   ├── RISC-V Embedded GCC/bin/riscv-none-embed-gcc      ← GCC8
│   ├── RISC-V Embedded GCC12/bin/riscv-wch-elf-gcc      ← GCC12
│   ├── RISC-V Embedded GCC15/bin/riscv32-wch-elf-gcc    ← GCC15
│   └── arm-none-eabi-gcc/bin/arm-none-eabi-gcc
└── OpenOCD/
    ├── sub_manifest.json
    └── OpenOCD/bin/openocd + wch-*.cfg
```

- **识别**：顶层 `Toolchain/sub_manifest.json` + `OpenOCD/` + 至少一个真实存在的 gcc
  （不是仅有清单条目）。代次恒记为 **MRS2**——官方 `MRS_Toolchain_*` 包就是 MRS2 代工具链。
- **没有 SDK/芯片库、没有 IDE、没有自带 make**：`chips` 查不到芯片库；构建用系统 make；
  新建工程模板只能用 MRS3 IDE 的 `SDK/default` 或 Windows 安装。
- `PAXHeaders` / `__MACOSX` 之类解包残留忽略，不影响识别。

**行为逆向的权威来源**：`<安装根>/resources/app/extensions/mrs-team.mrs-vscode/out/extension.js`
（macOS：`<.app>/Contents/Resources/app/extensions/...`）——MRS IDE 功能的实现 bundle
（webpack 压缩单行 JS，约 3.6MB，阅读前先格式化/搜串定位；两代/三平台同构）。工程读写行为、引号/宏处理（`EPMacroStrResolve`）、C/C++ 类型判定
（`getEclipseProperties` 认 `ccnature`）等结论都出自它——遇到"MRS2 到底怎么处理 X"的疑问，
直接查它比猜测可靠。

## 代次判定（MRS2 vs MRS3）

布局同构，探测靠品牌文件（优先级从高到低，与 MRVC `detectFlavor` 一致）：

1. `<安装根>/resources/app/product.json` 的 `mrsVersion` **主版本号**——`"2.x"` → MRS2，
   `"3.x"` → MRS3。两代都带这个键，是权威来源（MRS3 三平台实测 `"3.0.0"`）。macOS 的路径是
   `<.app>/Contents/Resources/app/product.json`；Linux 的 tar 与 .deb 布局相同。
2. 同文件的 `nameShort` / `applicationName` 品牌串（含 `Studio 3`/`studio-3` → MRS3）。
3. 安装根下**启动器**是否存在（仅作兜底）：
   - Windows：`MounRiver Studio 3.exe` / `MounRiver Studio 2.exe`；
   - Linux：`mounriver-studio 3` / `mounriver-studio 2`（根目录 ELF；.deb/tar 的 `bin/` 下
     另有一个同名 shell 包装脚本，两种布局都认）；
   - macOS：`Contents/MacOS/Electron`（`CFBundleExecutable=Electron`），**名字不带代次**，
     只能靠 product.json——macOS 上启动器探测返回 null，不要据此判代。
4. 全无 → 记为 unknown（手工拼装的安装）；`manifest.json` 两代通用，不能用来区分代次。

## 安装路径的来源（按优先级）

1. `--mrs2 <路径>` 参数（**MRS2/MRS3、IDE/纯工具链通用**，自动识别代次与布局）。
2. 环境变量 `MRS2_HOME`，其次 `MRS3_HOME`。
3. 兜底探测**本机平台**的惯例位置（只认这些通用约定，不枚举其他目录）：
   - Windows：`C:\MounRiver\MounRiver_Studio2`、然后 `C:\MounRiver\MounRiver_Studio3`
     （MRS2 在前）；
   - Linux：`/usr/share/MRS3/MRS-linux-x64`（.deb 实装路径；tar.xz 解包目录因用户自选，
     **没有惯例位置**，必须显式提供）；
   - macOS：`/Applications/MounRiver Studio 3.app`（也接受其 `Contents/`）；
   - **纯工具链包（`MRS_Toolchain_*`）在任何平台都没有惯例位置**，必须显式提供或设环境变量。
4. 以上都不存在 → 报错并提示：**需要已安装 MounRiver Studio 2/3，或解包 MRS_Toolchain_*，
   请提供路径**。MounRiver Studio 1 的安装目录没有这一层资源结构，会被判定标志自然排除。

判定：
- **IDE**：`<候选>/resources/app/resources/<win32|linux|darwin>/components/WCH/manifest.json`
  存在即命中；macOS 也接受直接给 `.app` 或 `.app/Contents`。
- **纯工具链**：`<候选>/Toolchain/sub_manifest.json` + `<候选>/OpenOCD/` + 至少一个真实存在的
  gcc（仅有清单条目不算）。
- 允许用户指到深层目录（平台层 `.../resources/<layer>`、`resources/app`、`Contents` 等）：
  定位逻辑会向上最多 8 级找布局，找到后自动还原安装根。Windows 的
  `...\resources\app\resources\win32` 与 Linux 的 `.../resources/app/resources/linux` 都等价。
- **解析不依赖宿主平台**：在 Windows 上也能指向 Linux/macOS 解包树做 `show`/`toolchain`/`chips`
  （只读解析；不能执行另一平台的二进制）。反之亦然。

## 架构门禁（Linux / macOS 必查）

Windows 工具链没有架构变体（都 x86），非 Windows 必须核对**已解析 gcc 的二进制头**与本机
`process.arch` / `uname -m`：

| 包 | 架构（实测） |
|---|---|
| MRS3 Linux IDE（tar.xz 与 .deb） | 全 x86-64 ELF（启动器、gcc、openocd、make 同） |
| MRS3 macOS IDE（arm64 包） | Mach-O **arm64 专用**（Electron、GCC12/15、openocd、make）；GCC8 与 ARM 是 x86_64（Rosetta 可跑） |
| MRS2 代 macOS 纯工具链 V2.4 | **混合架构**：GCC8（`riscv-none-embed-*`，含其 gdb）与 `arm-none-eabi-*` = **x86_64**；GCC12（`riscv-wch-elf-*`，含其 gdb）、GCC15（`riscv32-wch-elf-*`）与 **OpenOCD = arm64**；全部单架构 Mach-O，无 universal |
| MRS2 代 Linux 纯工具链 V2.4 | 全 x86-64 ELF |

- 判定读 ELF `e_machine`（0x3E=x86-64 / 0xB7=AArch64）或 Mach-O `cputype`
  （0x00000007=x86_64 / 0x0100000C=arm64，含字节序）；universal FAT 直接放行，读不出的
  头放行（不能因读不出就拒绝安装）。
- 不符 → 报 `wrong-arch` 并在构建前拦截。典型：**Intel Mac 装 arm64 MRS3**、
  **Apple Silicon 用 V2.4 包的 GCC8 判架构**（GCC8 是 x86_64，会整包被拒；但同一包的
  GCC12/15 是 arm64，手工指定这两个工具链仍可用）。
- Intel Mac 用 V2.4 mac 包：GCC8/ARM 可跑，**GCC12/15 是 arm64，必然 `Bad CPU type`**；
  且包里的 **OpenOCD 也是 arm64**——Intel Mac **只能编译，烧录/调试不可用**。
  Apple Silicon 用 V2.4 mac 包：GCC12/15 与 OpenOCD 可跑，GCC8/ARM 需 Rosetta（且按 GCC8 做
  门禁的工具会先拒绝整包）。所以 **Intel Mac 只有纯工具链形态、且只覆盖编译**，Apple Silicon
  优先 MRS3 arm64 IDE（链路完整）。
- Linux 上若把 Windows/Mac 树拷过来，二进制架构不符同样在构建时失败（`Exec format error`）。

## sub_manifest.json（工具链清单）

`Toolchain/sub_manifest.json` 的 `details[]` 是工具链唯一可信来源（IDE 在
`<平台层>/components/WCH/Toolchain/`，纯工具链包在 `<根>/Toolchain/`；**三平台 schema 与
相对位置相同**）。关键字段：

```json
{
  "name": "GCC12",
  "type": "RISC-V",
  "version": "v1.4",
  "path": "./RISC-V Embedded GCC12",
  "compiler_c_executable":  { "folder": "./bin", "name": "riscv-wch-elf-gcc" },
  "compiler_cpp_executable":{ "folder": "./bin", "name": "riscv-wch-elf-g++" },
  "debugger_executable":    { "folder": "./bin", "name": "riscv-wch-elf-gdb" },
  "other_tool_dir": "bin",
  "other_tool_prefix": "riscv-wch-elf-"
}
```

要点：
- **prefix 区分工具链代际**：GCC8 = `riscv-none-embed-`；GCC12 = `riscv-wch-elf-`；
  GCC15 = `riscv32-wch-elf-`。`.cproject` 里 `option.command.prefix` 存的就是这个值——
  切换工具链时必须同步改它，否则生成的命令行找不到编译器。
  **MRS3 的 sub_manifest 结构与此完全一致、prefix 逐项相同**（两代实机核对），
  同一工程在两代 IDE 里选同一工具链，编译命令行不变。
- **清单里的编译器名是裸名（不带 `.exe`）**：Windows 的 make 配方依赖 CreateProcess/PATHEXT
  补后缀，POSIX 直接用裸名。写 makefile 时保持裸名；只有给 cpptools 的 `compilerPath`
  这类会 stat 文件的消费者才需要补真实后缀（Windows `.exe`，POSIX 不补）。
- status=2 表示已安装。`.7z` 旁置文件是未解压的备份包，忽略。
- `march` 扩展语法依赖工具链代际：GCC8 用尾缀式 `rv32imacxw`；GCC12/15 用
  `rv32imac_zba_zbb_zbc_zbs_zmmul_xw`（下划线形式），见 build.md。

## 芯片库（SDK/default）数据文件

**只有完整 IDE 安装才有 `components/WCH/SDK/default`**；纯工具链包（`MRS_Toolchain_*`）没有
SDK，`chips` 命令会明确报"纯工具链包不含 SDK/芯片库"。Linux/macOS 的 MRS3 IDE 带完整
SDK，其 `<系列>-flash.json` / `<系列>-targetProcessor.json` 结构与 Windows 相同。

`<系列>-flash.json`（系列级，所有下载能力判断的来源）：

```json
{
  "type": "CH32V30x",
  "id": 6,                          ← WCH-Link chipID（McuCompilerDll 参数）
  "flash_address": "0x08000000",    ← 默认下载地址
  "support_readProtectOpts": true,  "support_eraseCodeFlash": true,
  "support_memoryAssign": true,     "support_eraseAll": true,
  "support_program": true,          "support_verify": true,
  "support_resetRun": true,         "support_spiPrintf": true,
  "support_debugInterfaceMode": false
}
```

`<系列>-targetProcessor.json`（新建工程时的默认 ISA/ABI）：

```json
{
  "architecture": "rv32i", "multiply_extension": true, "atomic_extension": true,
  "compressed_extension": true, "extra_compressed_extension": true,
  "floating_point": "none", "integer_ABI": "ilp32", "floating_point_ABI": "none",
  "small_data_limit": 8, "save_restore": true, "tuning": "default", "code_model": "default"
}
```

- 芯片型号清单 = `<系列>\<RTOS>\NoneOS\*.zip` 的文件名（NoneOS 的 zip 对应具体封装型号，
  如 `CH32V307VCT.zip`；其他 RTOS 目录只有一个全家桶 zip，不算型号）。
- 挑选 RTOS 目录 = 新建工程向导的第二级（NoneOS / FreeRTOS / RT-Thread / TencentOS / Harmony LiteOS-M / uCOS-II…）。
- 模板 zip 解压即得完整工程（含 .project/.cproject/.launch/.template），新建工程 = 解压 +
  写空 `<新名>.wvproj` + 把模板显示名改成新名（改名级联见 project-formats.md）。

## MRS Tools 菜单的 GUI 工具（启动器路径）

WCH-LinkUtility（`Others\SWDTool\default\WCH-LinkUtility.exe`）、WchIspStudio
（`Others\WCHISPTool\default\`）、WCHTouchKeyTool（`Others\WCHTouchKeyTool\default\`）、
WCHGUIDesigner（`Others\WCHGUIDesigner\default\`）、HexBinStudio（`others\HexBinStudio\`）、
COMTransmit（`others\COMTransmit\`）——六项两代同路径，均可分离进程直接启动。
**MRS3 另有第七项「WCH 工具集」**（`Others\WCHToolKit\default\WCHToolKit.exe`，Electron 应用，
WCH 工具的统一入口）——MRS2 没有该组件，菜单里也不出现（调用方按生效代次门控）。
**以上 GUI 工具全部只在 Windows 安装里提供**：Linux/macOS 的 `Others/` 只有
`CommunicationLib` / `Firmware_Link` / `IQMath` / `WCHAgent`，WCH-LinkUtility、WCHISPTool、
WCHTouchKeyTool、WCHGUIDesigner、WCHToolKit、HexBinStudio、COMTransmit 全部缺席；调用方按
组件存在性降级为"该平台不提供"，不要拼一个不存在的 `.exe` 路径。
涉及读保护开关、调试器模式切换、固件升级等深度操作时优先让用户用 WCH-LinkUtility（Windows）。

## PATH 组装（构建/烧录时）

Windows（分隔符 `;`）：

```
<工具链目录>\bin ; <win32>\others\Build_Tools\Make\bin ; %PATH%
```

make 必须用安装自带的（GNU make for Windows，依赖同目录 sh.exe/rm.exe）；手动组装命令直接调
gcc 时则只需工具链 bin。

Linux / macOS（分隔符 `:`）：

```
<工具链目录>/bin:<res>/others/Build_Tools/Make/bin:$PATH
```

- IDE 自带 `make`（与 IDE 同架构），但仍需系统 `sh`/`bash`；纯工具链包没有 make，
  确保系统 PATH 有 GNU make（`make --version` 确认是 GNU make 而非 BSD make）。
- 工具链与 openocd 都是裸名，无 `.exe`；从 zip/Windows 拷贝后先确认可执行位
  （`chmod +x`），否则报 `Permission denied`。
- 两代/三平台的构建环境等价：同一工程分别用 MRS2/MRS3 构建，仅 ELF 字节有少量差异
  （工具链补丁级不同），配合 MRS3 的 GCC12 主链路实编通过。
