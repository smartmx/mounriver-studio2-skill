# MRS2/MRS3 安装目录结构与工具链解析

所有工具组件都在 `<安装根>\resources\app\resources\win32\` 下（MounRiver 本体是 VSCode 内核
套壳，这一层是它的资源目录）。**MRS2 与 MRS3 的目录结构同构**——下面整棵树对两代都成立，
工具链前缀、make bundle、OpenOCD、芯片库全部通用；区分点只有品牌/版本判定与个别组件位数
（见「代次判定」与树内标注）。`<安装根>` 指定位到的 MounRiver Studio 2/3 安装目录
（来源见下方「安装路径的来源」）。

## 目录总览

```
<安装根>\                                  ← 用户提供的 MounRiver Studio 2/3 安装根
└── resources\app\resources\win32\         ← 资源层（两代同构）
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

**行为逆向的权威来源**：`<安装根>\resources\app\extensions\mrs-team.mrs-vscode\out\extension.js`
——MRS2 IDE 功能的实现 bundle（webpack 压缩单行 JS，约 3.6MB，阅读前先格式化/搜串定位；
两代同构）。工程读写行为、引号/宏处理（`EPMacroStrResolve`）、C/C++ 类型判定
（`getEclipseProperties` 认 `ccnature`）等结论都出自它——遇到"MRS2 到底怎么处理 X"的疑问，
直接查它比猜测可靠。

## 代次判定（MRS2 vs MRS3）

布局同构，探测靠品牌文件（优先级从高到低，与 MRVC `detectFlavor` 一致）：

1. `<安装根>\resources\app\product.json` 的 `mrsVersion` **主版本号**——`"2.x"` → MRS2，
   `"3.x"` → MRS3。两代都带这个键，是权威来源（MRS3 实测 `"3.0.0"`）。
2. 同文件的 `nameShort` / `applicationName` 品牌串（含 `Studio 3`/`studio-3` → MRS3）。
3. 安装根下启动器 exe 是否存在：`MounRiver Studio 3.exe` / `MounRiver Studio 2.exe`。
4. 全无 → 记为 unknown（手工拼装的安装）；`manifest.json` 两代通用，不能用来区分代次。

## 安装路径的来源（按优先级）

1. `--mrs2 <路径>` 参数（**MRS2/MRS3 通用**，自动识别代次）。
2. 环境变量 `MRS2_HOME`，其次 `MRS3_HOME`。
3. 兜底探测 WCH 安装器的默认位置：`C:\MounRiver\MounRiver_Studio2`、然后
   `C:\MounRiver\MounRiver_Studio3`（MRS2 在前；只认这两个通用约定，不枚举其他目录）。
4. 以上都不存在 → 报错并提示：**需要已安装 MounRiver Studio 2 或 3，请提供安装路径**。
   MounRiver Studio 1 的安装目录没有这一层资源结构，会被判定标志自然排除。

判定：`<候选>\resources\app\resources\win32\components\WCH\manifest.json` 存在即命中；
也接受用户直接填到 `...\win32` 这一层（此时安装根 = 往上 4 级：win32 → resources → app → 安装根）。

## sub_manifest.json（工具链清单）

`Toolchain\sub_manifest.json` 的 `details[]` 是工具链唯一可信来源，关键字段：

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
- status=2 表示已安装。`.7z` 旁置文件是未解压的备份包，忽略。
- `march` 扩展语法依赖工具链代际：GCC8 用尾缀式 `rv32imacxw`；GCC12/15 用
  `rv32imac_zba_zbb_zbc_zbs_zmmul_xw`（下划线形式），见 build.md。

## 芯片库（SDK/default）数据文件

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
涉及读保护开关、调试器模式切换、固件升级等深度操作时优先让用户用 WCH-LinkUtility。

## PATH 组装（构建/烧录时，两代同理）

```
<工具链目录>\bin ; <win32>\others\Build_Tools\Make\bin ; %PATH%
```

make 必须用安装自带的（GNU make for Windows，依赖同目录 sh.exe/rm.exe）；
手动组装命令直接调 gcc 时则只需工具链 bin。
两代安装的构建环境完全等价：同一工程分别用 MRS2/MRS3 构建，仅 ELF 字节有少量差异
（工具链补丁级不同），配合 MRS3 的 GCC12 主链路实编通过。
