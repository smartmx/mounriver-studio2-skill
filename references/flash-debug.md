# MRS2/MRS3 烧录、调试与芯片操作

> **实证版本**：本篇结论核对于 **MRS2 `2.0.0`** 与 **MRS3 `3.0.0`** 的 Windows 安装及 V300
> 解包树；OpenOCD = `0.11.0+dev-snapshot`（2026-08-25 构建，两代同版）。底层协议
> （FlashOperationExB 位掩码、SDI PRINT、doUpdate、wlinke 命令族）与 DLL/OpenOCD 二进制绑定，
> **未来 MRS 版本的行为未知**——降级顺序：①先按所属大版本（MRS2/MRS3）的已知协议/路径尝试；
> ②行为对不上时以实际探测为准（定位安装 → 检查 OpenOCD/cfg/DLL 是否在位 → 小步试跑），
> 再继续。

## 烧录引擎（OpenOCD + WCH-Link）

可执行文件：`$MRS/resources/app/resources/<平台层>/components/WCH/OpenOCD/OpenOCD/bin/openocd`
（Windows `openocd.exe`，Linux/macOS `openocd`；纯工具链包在
`<根>/OpenOCD/OpenOCD/bin/openocd`）。MRS2/MRS3 同路径、同为 openocd 0.11.0+dev-snapshot；
Windows 是 32 位宿主，Linux x86-64 / macOS arm64 与 IDE 同架构。**cfg 集随包略有差异**：
Linux/macOS 可能没有 `wch32f103.cfg` / `openocd_gdlink_riscv.cfg`，macOS 多
`openocd_jlink.cfg`（以实际 `bin/` 目录为准，不要硬编码完整列表）。

板配置（-f 顺序敏感，板 cfg 在前、脚本在后）：

| cfg | 场景 |
|---|---|
| `wch-riscv.cfg` | 默认 RISC-V（CH32V 系列、CH56x/57x/58x/59x） |
| `wch-dual-core.cfg` | CH32H417 双核（V3F/V5F；core1 flash bank 在 0x00005000） |
| `wch-arm.cfg` / `wch32f103.cfg` | ARM 系列 |
| `openocd_jlink.cfg` / `openocd_gdlink_riscv.cfg` | 第三方调试器 |

**同名 cfg 在安装树里有多份且内容各异**：`OpenOCD/bin/wch-riscv.cfg`（IDE/烧录同源——自写
脚本用它）、`OpenOCD/scripts/board|wch/`、`share/openocd/scripts/...` 下的同名文件实测 md5
互不相同。诊断与手写脚本一律取 `bin/` 旁那份。

### 平台差异（烧录 / 调试）

| 能力 | Windows | Linux | macOS |
|---|---|---|---|
| OpenOCD CLI | `openocd.exe` | `openocd` | `openocd` |
| WCH-LinkUtility（GUI） | 有（`Others/SWDTool`） | 无 | 无 |
| wlink 底层操作库 | `McuCompilerDll.dll`（P/Invoke，实测） | `libmcuupdate.so`（进程内 FFI，**未实测**） | `libmcuupdate.dylib`（进程内 FFI，**未实测**） |
| USB 权限 | WCH 驱动 | udev 规则 | 驱动/权限 |
| 实测状态 | 完整 | OpenOCD 路径在位，USB 烧录**未实测** | **未实测 / 实验性** |

**Linux 烧录前**（MRS3 的 tar.xz / deb 包在 `beforeinstall/` 提供）：

1. 把 `50-wch.rules`、`60-openocd.rules` 装到 `/etc/udev/rules.d/`；规则覆盖
   `1a86:8010`、`1a86:8012`、`4348:55e0`，`GROUP="plugdev"`。
2. `sudo udevadm control --reload-rules && sudo udevadm trigger`；当前用户加入 `plugdev`
   （或按发行版用 `dialout`/`uucp`）。
3. `beforeinstall/` 还带 `libhidapi-*`、`libusb-1.0`、`libjaylink`、`libmcuupdate`、
   `libncurses.so.5.9`、`libtinfo.so.5.9`；OpenOCD 缺库时用 `LD_LIBRARY_PATH` 指向它，
   或装系统 `libncurses5`/`libtinfo5`。
4. 不要用 `sudo` 跑整个构建；只给 openocd 设备权限。
5. 包根 `beforeinstall/start.sh` 会做同样的系统级准备（`cp lib* /usr/lib` + `ldconfig`、复制
   udev 规则、设置 `chrome-sandbox` setuid），需要 sudo；不想跑脚本就按上面 1–3 手工做。

**macOS**：`openocd` 可执行文件在位，但 WCH-Link 的 USB 通道与烧录流程**未实测**；交付/发布时
标"实验性"，需真机验证。从网络下载/拷入的 `.app` 带 quarantine 属性，放入 `/Applications` 后
首次打开要过 Gatekeeper（右键打开或在"隐私与安全性"放行）——命令行工具链不受影响。
**WSL2**：USB 用 usbipd-win 直通；构建链路可全程在 WSL2 跑，只有
烧录需要真机或直通。

### 地址规则（拿错会静默不烧）

1. `.template` 的 `Address=`（格式 `0x` + 1-8 位 hex）优先。
2. 缺省时查芯片库 `<系列>-flash.json` 的 `flash_address`。
3. 再缺省按源文件名前缀推断：`startup_ch32v30x_*.S`/`ch32v30x_*.c` 类前缀 →
   **CH5x 无线系列（CH56x/57x/58x/59x，CH564 除外）= 0x00000000；CH32x、CH564、CH641/643 =
   0x08000000**。

### WCH OpenOCD 的双重地址语义（关键，2026-07 版 openocd 实证）

下载地址要到达 OpenOCD **两次**：

1. `wlink_set_address <bank>` —— 成为 flash **bank 基址**。WCH 驱动在 `init` 探测时采样它
   （`ch32vx_probe` 里 `bank->base = wlink_address`），所以这条必须放在 `init` **之前**。
2. `program <文件> <offset>` —— offset 是 write_image 的**写入偏移**。

WCH 官方 hex 镜像链接在 0x00000000（ELA 记录给出最低数据地址），而 bank 基址是非零下载地址；
`program` 不带 offset 时镜像各段落在 bank 窗口之外 → `no flash bank found for address
0x00000000`，**什么都不写也不报错退出**。正确换算：

- 设下载地址 A，hex 自身最低数据地址 H（Intel HEX type-04 ELA + type-00 数据记录算最小值）：
  - H == 0（常见）：`wlink_set_address A`，`program "fw.hex" A`
  - H > 0（自定义链接脚本 ORIGIN 非零，hex 已在物理地址）：`wlink_set_address A`，offset = A − H；
    若 A < H，则 `wlink_set_address H`、offset = 0
  - .bin 无内部地址：offset = A

### 烧录脚本（写入 obj/mrs2_flash.cfg，ANSI 编码，路径用正斜杠）

普通（非全片擦除）：

```
wlink_set_address 0x08000000
program "E:/path/obj/demo.hex" 0x08000000 verify reset exit
```

全片擦除（`.template Erase All=true`；不能简单在 program 前插擦除——OpenOCD 的 program
proc 内部自带 `init`，必须展开整个流程）：

```
wlink_set_address 0x08000000
init
reset init
flash erase_sector 0 0 last          ← 双核再加一行 flash erase_sector 1 0 last
flash write_image erase "E:/path/obj/demo.hex" 0x08000000
verify_image "E:/path/obj/demo.hex" 0x08000000
poll off
reset run
shutdown
```

调用：`openocd.exe -f <板cfg> -f <脚本cfg>`。自定义板 cfg（用户自备）时 eraseAll 的 bank 数
按 1 处理，避免对不存在的 bank 1 执行 erase_sector 导致脚本中止、后续 write_image 不执行。

`Programming Started / Finished / Verified OK` 这些字样是 openocd **内嵌 `program` proc 的
echo**（proc 内部：花括号包路径 `set filename \{...\}` → `init`/`reset init` → write_image
erase → `verify_image` → `poll off` + `reset run` → `shutdown`）。自己展开流程的手写脚本
**没有这些字样属正常——静默≠没写**，用 `verify_image` 实证（实测 eraseAll 分支写后 verify
0 diff）。另：openocd 的输出**不要接管道截断**（`head` 等 SIGPIPE 会在写操作中途杀进程，
把 Link 打成 `unknown WCH-LINK` 卡死态、只能拔插 USB 恢复）——诊断一律重定向到文件。

## WCH-Link 底层操作（读保护/chipID/存储分配等）

GUI 路径：`Others/SWDTool`（WCH-LinkUtility）——读保护开关、调试器模式切换、固件升级等
深度操作优先引导用户用它。**该 GUI 只在 Windows 安装里提供**；Linux/macOS 没有它，底层操作
走下面的原生库。

**三平台同一套原生库**：wlink 底层操作的事实引擎在
`components/WCH/Others/CommunicationLib/default/`，按平台换文件名（MRS 自己的扩展在 POSIX 上
就是进程内 FFI 加载它们）：

| 平台 | 库文件 | 同目录依赖 / 附带物 |
|---|---|---|
| Windows | `McuCompilerDll.dll` | （MRS2 32 位 / MRS3 64 位，见下） |
| Linux | `libmcuupdate.so` | `libhidapi-*`、`libjaylink`、`libusb-1.0`、`libncurses.so.5.9`、`libtinfo.so.5.9`；还有 `50-wch.rules` / `60-openocd.rules` |
| macOS | `libmcuupdate.dylib` | `libhidapi*.dylib`、`libusb-1.0.0.dylib` |

- **导出三平台同名**（逐符号实证：ELF `.dynsym` / PE 导出表 / dylib 符号串）：
  `MRSFunc_*` 操作族——`QueryRProtect` / `EnableRProtect` / `DisableRProtect` /
  `GetLinkedMCUID` / `ClearCodeFlash` / `GetMemType` / `SetMemType` / `DisableDbgInterface` /
  `FlashOperation(Ex…)` 等——加上 `McuCompiler_SetTargetChip`。**Windows 版另有一大批
  `McuCompiler_*` 助手（`GetChipInfo` / `EnumLink` / `SetLinkIndex` / `ReadDevMemory` /
  `GetFlashSum` 等）POSIX 版没有**——跨平台脚本只用两边都有的导出；POSIX `.so` 还泄漏大量
  内部符号，不要依赖。
- 调用前置：先 `McuCompiler_SetTargetChip(chipId, dbgMode)`（dbgMode 常规 0）；随后的操作签名是
  `(chipId, clkSpeed)`——`ClearCodeFlash` 另加 `mode`、`GetLinkedMCUID` 只要 chipId。chipID 取
  芯片库 `<系列>-flash.json` 的 `id`；能力开关（`support_readProtectOpts` /
  `support_eraseCodeFlash` / `support_memoryAssign` / `support_eraseAll` …）为 false 的操作
  在该芯片上不可用，UI 上应禁用。
- **调用序列**（以 MRS 自家扩展的实现为权威，从其 bundle 实证）：`SetTargetChip → doUpdate →
  目标操作`——`doUpdate` 是扩展 JS 层的设备初始化封装。手工 FFI/P-Invoke 走精简序列
  （`SetTargetChip + 操作`）是 MRVC 先例；若某平台/某芯片上操作整体失败，先回 MRS 扩展
  bundle（`extensions/mrs-team.mrs-vscode/out/extension.js`）对照 `doUpdate` 做了什么再补齐。
- **Windows 命令行路径（MRVC 先例，实测）**：用与库**位数匹配**的 PowerShell P/Invoke
  （取 `Others\CommunicationLib\default\` 那份；OpenOCD bin 里另有一份 32 位拷贝、匹配 32 位
  openocd.exe，不要拿它当桥）：
  - **宿主位数随安装代次**：MRS2 的 DLL 是 32 位 → 用
    `%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`；MRS3 的是 64 位 → 用
    `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`。位数不匹配加载不了 DLL；
    稳妥做法是读 DLL 的 PE 头 Machine 字段选宿主（0x14c=32 位 / 0x8664=64 位）。
  - `Add-Type` 内联 C#：`[DllImport("McuCompilerDll.dll", CallingConvention = CallingConvention.StdCall)]`
    声明 int 参数导出函数；真正导出名是 `MRSFunc_*`/`McuCompiler_*`，托管名经 `EntryPoint`
    映射，不写 EntryPoint 调用的就是根本不存在的名字。
  - PS 输出按"最后一行是 JSON"提取（`ConvertTo-Json` 会把非 ASCII 转义成 `\uXXXX`，天然避开
    代码页问题）；PS 脚本文件要带 UTF-8 BOM 写入。每次调用都有 1-3 秒 Add-Type 编译开销。
  - 调用约定注意：MRVC 按 StdCall 声明且工作正常，但 MRS 用 koffi 绑定（x86 上 cdecl 常见），
    怀疑崩溃时先用 dumpbin 核对导出符号的调用约定。
- **Linux/macOS 命令行路径**：任何进程内 FFI 都能调（Python 用 `ctypes.CDLL`；Node 侧可直接
  复用 MRS 自带扩展捆绑的 koffi——`extensions/mrs-team.mrs-vscode/out/koffi/`，MRS 自己的
  扩展就是这么进程内加载的）。注意 `dlopen` **不会自动搜索同目录依赖**——先
  `LD_LIBRARY_PATH=<...>/CommunicationLib/default`（macOS 另有 `DYLD_LIBRARY_PATH`）或显式
  预加载依赖库再加载主库。**未经真机实测**：库、符号、加载路径都已就位，烧录/读保护的
  实跑结果待回报，交付时标"已实现未实测"。
- **纯工具链包（`MRS_Toolchain_*`）没有 `Others/CommunicationLib`**——Linux/mac 纯工具链
  形态下这套底层操作不可用，只剩 OpenOCD 命令行（见上）。

### 目标芯片一致性（下载前校验，MRS 原生机制）

- MRS 的下载路径把工程 chipId（SDK `<系列>-flash.json` 的 `id` 字段，MRS TS 侧读作
  flashControl.id）直接交给 `MRSFunc_FlashOperationExB`；芯片不符时 DLL 返回 **10006**
  （"Chip type mismatch."）——MRS 自身**没有**预查询/预比对。手工流程（FFI 或 OpenOCD 烧写）
  应在烧写前用 `MRSFunc_GetLinkedMCUID()`（无参）与工程 chipId 比对——这是 MRS 报"当前芯片"
  的同一函数、同一 id 空间。
- **信任门（必读）**：裸 `GetLinkedMCUID` 可能返回 **Link 自身的 id**（LinkE 2.23 实测裸答
  2/6——而 **6 恰是 CH32V30x 的家族 id**）。采信前必须先跑
  `McuCompiler_OpenDevice() → McuCompiler_CompareVersion(<wcfg>) == 0 → McuCompiler_CloseDevice()`
  （MRS2 getChipID RPC 同款前置；实测该序列不污染 Link 状态、紧接烧录正常）。家族 id 会跨
  系列共享（**78 = CH32M007 与 CH32V002/4/5/6/7**）——不匹配提示要列出全部候选型号。

### FlashOperationExB：一条命令下发烧录选项（位掩码）

`MRSFunc_FlashOperationExB(chipID, clkMode, option, addr, hexPath)`（全 int 除路径；MRS 扩展
downloadProject 实证，MRS2/MRS3 同构）的 `option` 位序：

| bit | 值 | 含义 |
|---|---|---|
| 7 | 128 | disablepowerout |
| 6 | 64 | clearcodeflash（"断电/复位后擦除"开关） |
| 5 | 32 | disablecodeprotect |
| 4 | 16 | **sdiPrintf**（使能 SDI 打印，见下节） |
| 3 | 8 | erase |
| 2 | 4 | program |
| 1 | 2 | verify |
| 0 | 1 | reset |

- 串口 ISP（无 WCH-Link 的裸串口设备）走
  `MRSFunc_FlashOperationExternal(chipID, mode, opt, addr, binPath, asmPath)`：1-wire →
  `mode 10+n`、2-wire → `20+n`；`.bin` 路径必须 0x 地址。
- 非 WCH-Link 下载器时 MRS 直接 spawn 厂商 GUI（WchIspStudio / WCH-LinkUtility），参数取自
  `.cproject` flashConfig。
- `MRSFunc_ClearCodeFlash(chipID, clk, mode)` 的 `mode`：0=By Pin NRST、1=By Power——IDE 的
  "断电复位/复位后擦除"动作就是它（擦除能力与 OpenOCD 路径对等）。

### SDI PRINT（printf 走调试口，MRS2/MRS3 同构）

- **固件侧**：SDK `debug.c` 的 `SDI_Printf`（`SDI_PRINT` 宏，写调试模块打印寄存器）。
- **使能侧（FFI）**：下载配置 `SDI Printf` 复选框（.cproject flashConfig `sdiPrintf`）→ 拼
  进 FlashOperationExB 的 **bit16** → DLL 向 Link 发协议串 **`SDI_PRINTF ENABLE`**；成功输出
  `"Enable SDI print Finished"`，专用错误码 **118**（"Failed to enable SDI print function"）。
  导出表另有 `McuCompiler_SetSDIPrn`（0=使能 / 1=禁能）。
- **OpenOCD 同款通道**：WCH fork 内置 **wlinke 适配器 + sdi 传输层**——安装自带的
  `wch-riscv.cfg` 本身就是 `adapter driver wlinke` + `transport select sdi`（常规烧录已经跑在
  这条通道上）。wlinke 驱动注册命令族：`sdi_printf / two_wires / dbgtool / wlink_set_index /
  wlink_set_address / pow3v3 / pow5v / code_erase / chip_id / page_erase / disabledebug /
  noload / rst_set`。`sdi_printf` 须在 `init` **之前**调用（只是设置会话标志）；真机实测
  sdi 通道切换会引起 USB 重枚举，不要在下载会话中途切。
- **读取端**：打印流由 WCH-Link 转成 **CDC 虚拟串口**——选 `VID_1A86&PID_8010` 的 **MI_01**
  接口；EVB 板载的 `PID_55D3`（CH343）是板载串口**不是 SDI 口**。任意串口终端打开即可（MRS
  内置 serialterminal 开的也是这个口；IDE 没有 SDI 专属读取通道）。监视器要在 `reset run`
  之前打开——下载后 Link 重枚举，需轮询等端口回来。

### WCH-Link 固件版本检查与升级（MRS 下载路径内置，doUpdate 规格）

MRS 下载前做固件检查（`McuCompiler_CompareVersion` + `wchlink.wcfg`），过旧时模态引导升级。
手工复刻要点（MRS3 扩展 doUpdate 逐行实证）：

- 导出签名：`OpenDevice()` / `CloseDevice()` 无参；`GetDeviceVersion(int*, int*)`（有效域
  10..99）；`CompareVersion(wcfgPath, int* out1, int* out2)`——0=免升、1=需升、其他=错误码，
  `out1[0]&255` = linkID（DLL 自己解析 wcfg 判型）；`SetIAPMode()`；`Update(firmwarePath,
  mode)`（0=阻塞主路径 / 1=IAP 分段变体）。
- **linkID → 型号 → payload**：0/1=WCH-Link（CH549；DAP 变体查 `CH549Ver_ARM`）；2/18=
  WCH-LinkE（chipType CH32V305 → **查 CH32V307 键**）；4=WCH-DAPLink（CH32V203）；5/133=
  WCH-LinkW（CH32V208）。
- **payload 目录**：`Others/Firmware_Link/default/`，命名 `FIRMWARE_<chipType>.BIN`（JS 探测
  `.BIN`，磁盘实体是 `.bin` 兜底；DAP 变体 `FIRMWARE_DAP_CH549.BIN`）——**引用安装组件**，
  不要拷进工程或打包。同目录 `wchlink.wcfg` = 期望版本表（`[Default]` 段 5 键；**两代安装的
  值可不同**：MRS2 实测 `CH32V307Ver=42`、MRS3=43——以实际读到的文件为准）。GUI 显示
  "v2.22" 与 wcfg 数值的刻度换算在 DLL 内部，勿自行比较。
- `WCHLinkEJtagUpdTool.exe` 是 LinkE→高速 JTAG SPI 的 **GUI 专用转换器**（硬编码固件名 + 改
  板警告），**不是 CLI 升级通道**——手工升级引导用户用 WCH-LinkUtility。

### 电源输出（wlinke 驱动 / DLL 导出）

wlinke 命令族含 `pow3v3` / `pow5v`；DLL 有 `McuCompiler_Opt33VOut` / `McuCompiler_Opt50VOut`。
仅带电源输出的 Link 型号支持（**LinkE / DAPLink / LinkW**；dbgtool/two_wires 不接电源）。
"掉电复位"= pow3v3/pow5v 两段式（先下电再上电）。

## 调试（gdb + OpenOCD server）

1. `openocd -f wch-riscv.cfg`（Windows `openocd.exe`；gdb server 3333 / telnet 4444 / tcl 6666）
2. `<工具链>/bin/riscv-wch-elf-gdb obj/<名>.elf`（Windows 是 `riscv-wch-elf-gdb.exe`）→
   `target extended-remote localhost:3333`
3. 断点符号名：入口是 `handle_reset`（.launch 的 stopAt），`set mem inaccessible-by-default off`、
   `set architecture riscv:rv32` 是常用客户端配置（见 .launch 的 gdbClientOtherCommands）。
4. 外设寄存器视图：芯片库 `<系列>xx.svd`。

## 下载失败速查

| 现象 | 原因/修复 |
|---|---|
| `no flash bank found for address 0x00000000` | hex 链接在 0 而 bank 基址非零：offset 要用 `A - H` 换算（见上） |
| 烧完校验失败/跑飞 | 双核工程用了单核 cfg；或擦除不完整（Erase All=true 才全片擦） |
| openocd 连不上（Failed to open WCH-Link） | 驱动/占用：WCH-LinkUtility 或别的 openocd 正占用设备；拔插重试 |
| Linux：`Permission denied` 打开 USB / `/dev/bus/usb` | 没装 `50-wch.rules`/`60-openocd.rules`，或用户不在 `plugdev`；见上「平台差异」 |
| Linux/macOS：`openocd: error while loading shared libraries` | 缺 `libhidapi`/`libusb`/`libjaylink`/`libncurses.so.5`；用 `beforeinstall/` 的库 + `LD_LIBRARY_PATH` 或装系统包 |
| Linux/macOS：`libmcuupdate.so/.dylib` 打不开 / undefined symbol | 底层库依赖未被搜索到：`LD_LIBRARY_PATH`（mac 另加 `DYLD_LIBRARY_PATH`）指向 `CommunicationLib/default`，或先显式加载依赖；纯工具链包没有此库 |
| `Chip type mismatch.`（错误码 10006） | 目标芯片与连接不符：烧写前用 `GetLinkedMCUID` 与工程 chipId 比对——必须先跑 OpenDevice→CompareVersion 信任门（裸查询可能答 Link 自身 id，6 与 CH32V30x 撞号） |
| 错误码 118 / SDI 打印无输出 | 使能失败或读取口选错：使能=FlashOperationExB bit16（`SDI_PRINTF ENABLE`）；输出口=Link CDC `VID_1A86&PID_8010` 的 **MI_01**，别选 EVB 板载 CH343（`PID_55D3`）；监视器须在 `reset run` 前打开 |
| Link 变 `unknown WCH-LINK` 卡死 | openocd 输出被管道截断（SIGPIPE 写中途杀进程）；拔插 USB 恢复，诊断一律重定向到文件再分析 |
| `targets` / `curstate` 恒 unknown | WCH 驱动不跟踪运行态——不能据此判停机/运行；写入是否成功用 `verify_image` 实证 |
| 下载报 WCH-Link 固件过旧 | MRS 下载前 `CompareVersion`+`wchlink.wcfg` 检查；手工升级引导 WCH-LinkUtility（payload 在 `Firmware_Link/default/`，见「固件版本检查与升级」） |
| macOS：`Bad CPU type in executable` | 在 Apple Silicon 用了 x86_64 工具链（或反之）；换对应架构的包/工具链 |
| Linux/macOS 找不到 WCH-LinkUtility | 该 GUI 只在 Windows 安装提供；POSIX 用 OpenOCD CLI（烧录通道未实测） |
| cfg 报错 unknown command | 地址参数格式错（必须 `0x` 开头 hex）；或 wlink_set_address 放到了 init 之后 |
| 路径含中文烧录失败 | cfg 文件按 UTF-8 写了（应 ANSI），或路径用了反斜杠（应正斜杠） |
| 读保护后无法再连 | 先用 WCH-LinkUtility 解保护（解除会全片擦除，数据不保） |
