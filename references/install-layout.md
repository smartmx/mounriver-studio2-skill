# MRS2 安装目录结构与工具链解析

所有工具组件都在 `$MRS2\resources\app\resources\win32\` 下（MRS2 本体是 VSCode 内核套壳，
这一层是它的资源目录）。下表路径已在 MRS2 2.x 实机核对。

## 目录总览

```
$MRS2\                                      ← 安装根（默认 C:\MounRiver\MounRiver_Studio2）
└── resources\app\resources\win32\
    ├── components\WCH\
    │   ├── manifest.json                   ← 安装完整性标志文件（探测用）
    │   ├── Toolchain\
    │   │   ├── sub_manifest.json           ← 工具链清单（唯一可信来源，见下）
    │   │   ├── RISC-V Embedded GCC\        ← GCC8 (v8.2)，prefix riscv-none-embed-
    │   │   ├── RISC-V Embedded GCC12\      ← GCC12 (v12.2)，prefix riscv-wch-elf-
    │   │   ├── RISC-V Embedded GCC15\      ← GCC15，prefix riscv32-wch-elf-（注意是 riscv32-）
    │   │   └── arm-none-eabi-gcc\          ← ARM 工具链
    │   ├── OpenOCD\
    │   │   └── OpenOCD\bin\
    │   │       ├── openocd.exe
    │   │       ├── wch-riscv.cfg           ← 默认 RISC-V 板配置
    │   │       ├── wch-dual-core.cfg       ← CH32H417 双核 (V3F/V5F)
    │   │       ├── wch-arm.cfg / wch32f103.cfg / openocd_jlink.cfg / openocd_gdlink_riscv.cfg
    │   │       └── McuCompilerDll.dll      ← WCH-Link 底层操作 DLL（32 位）
    │   ├── SDK\default\
    │   │   ├── ARM\<系列>\...              ← ARM 模板
    │   │   └── RISC-V\<系列>\<RTOS>\
    │   │       ├── <芯片型号>.zip          ← 每个芯片型号一个完整可编译模板工程
    │   │       ├── <系列>-flash.json       ← 下载地址/chipID/能力开关（系列级）
    │   │       ├── <系列>-targetProcessor.json ← ISA/ABI 默认值（系列级）
    │   │       └── <系列>xx.svd            ← 外设寄存器视图
    │   └── Others\
    │       ├── SWDTool\                    ← WCH-LinkUtility（调试器配置/固件升级 GUI）
    │       ├── CommunicationLib\default\   ← McuCompilerDll.dll + load.wcfg（wlink 桥用）
    │       ├── IQMath\                     ← WCH IQmath 库 (-lIQmath_RV32)
    │       ├── WCHISPTool\default\WchIspStudio.exe
    │       ├── WCHTouchKeyTool\default\WCHTouchKeyTool.exe
    │       ├── WCHGUIDesigner\default\WCHGUIDesigner.exe
    │       └── Firmware_Link\  WCHLinkEJtagUpdTool\
    └── others\
        ├── Build_Tools\Make\bin\make.exe   ← 还有 sh.exe rm.exe mkdir.exe echo.exe busybox.exe
        ├── COMTransmit\COMTransmit.exe     ← 串口调试
        ├── HexBinStudio\HexBinStudio.exe
        └── AssociateTool\  DemoLib\  ExTool\  KeilConvert\  LinkDrv\
```

## 安装目录探测算法

1. 显式参数 `--mrs2 <路径>` 优先。
2. 环境变量 `MRS2_HOME`。
3. 依次探测常见位置：`C:\MounRiver\MounRiver_Studio2`、`D:\MounRiver\MounRiver_Studio2`、
   `C:\MounRiver\MounRiver_Studio`（MRS1 无 win32 资源层，会被判定标志排除）。
4. 判定：`<候选>\resources\app\resources\win32\components\WCH\manifest.json` 存在即命中；
   也接受用户直接填到 `...\win32` 这一层（此时安装根 = 往上 3 级）。

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

## MRS2 Tools 菜单六个 GUI 工具

WCH-LinkUtility（`Others\SWDTool`）、WchIspStudio、WCHTouchKeyTool、WCHGUIDesigner、
HexBinStudio、COMTransmit——均可分离进程直接启动，路径见上表。涉及读保护开关、
调试器模式切换、固件升级等深度操作时优先让用户用 WCH-LinkUtility。

## PATH 组装（构建/烧录时）

```
<工具链目录>\bin ; <win32>\others\Build_Tools\Make\bin ; %PATH%
```

make 必须用 MRS2 自带的（GNU make for Windows，依赖同目录 sh.exe/rm.exe）；
手动组装命令直接调 gcc 时则只需工具链 bin。
