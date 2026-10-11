# MRS2 烧录、调试与芯片操作

## 烧录引擎（两条路线，先分清）

- **MRS2 IDE 的 Download 按钮不走 OpenOCD**：走 WCH 原生 DLL（见下"McuCompilerDll"节），
  OpenOCD 在 MRS2 里**只用于调试**。
- **命令行烧录走 OpenOCD + WCH-Link**（本 skill 的路线）：开放、可脚本化，cfg 语义全透明。

可执行文件：`$MRS2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin\openocd.exe`

板配置（-f 顺序敏感，板 cfg 在前、脚本在后）。**芯片系列不参与 cfg 选择**——选 cfg 只看内核
与核数，地址差异全部由 `.template` 的 `Address` 承载（CH58x=0x00000000、CH32V3xx/CH32H417
=0x08000000 等）：

| cfg | 场景 |
|---|---|
| `wch-riscv.cfg` | RISC-V 单核（CH32V 系列、CH56x/57x/58x/59x）——默认 |
| `wch-dual-core.cfg` | CH32H417 双核（V3F/V5F；core1 flash bank 在 0x00005000） |
| `wch-arm.cfg` / `wch32f103.cfg` | ARM 系列 |
| `openocd_jlink.cfg` / `openocd_gdlink_riscv.cfg` | 第三方调试器 |

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

## McuCompilerDll 原生操作（下载/读保护/chipID/存储分配）

GUI 路径：`Others\SWDTool`（WCH-LinkUtility）——读保护开关、调试器模式切换、固件升级等
深度操作优先引导用户用它。

命令行路径（MRS2 Download 按钮与 MRVC 先例）：32 位 PowerShell P/Invoke `McuCompilerDll.dll`
（在 `Others\CommunicationLib\default\`，OpenOCD bin 目录里也有一份）：

- 必须 32 位宿主：`C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`（64 位进程
  无法加载 32 位 DLL；MRS2 宿主本身是 32 位 Electron）。
- `Add-Type` 内联 C#：`[DllImport("McuCompilerDll.dll", CallingConvention = CallingConvention.StdCall)]`
  声明 int 参数导出函数；操作序列与 chipID 从芯片库 `<系列>-flash.json` 的 `id` 字段来。
- **一次完整下载的调用骨架**：`SetTargetChip(chipID, dbgMode)` → 操作 → 读保护类操作后
  **延时 200ms 回读确认**（状态非即时生效）。`MRSFunc_FlashOperationExB(chipID, clkSpeed,
  选项位掩码, address, file)` 是 MRS2 Download 的实际入口，位掩码：erase=8 / program=4 /
  verify=2 / reset=1（可按位组合）。
- 常用返回/状态语义：`QueryRProtect` 返回 **3=读保护使能、4=已解除**；`DisableDbgInterface`
  返回 3=芯片不支持该操作；`GetMemType` 返回值**十位=存储组别(A-F)、个位=选项序号**。
- 能力开关（`support_readProtectOpts` / `support_eraseCodeFlash` / `support_memoryAssign` /
  `support_eraseAll` …）为 false 的操作在该芯片上不可用，UI 上应禁用。
- WCH-Link 自身有**两套固件模式**（FIRMWARE_CH549 / DAP_CH549.bin 两阶段互切）——Target
  Mode 切换不要用 DLL 硬做，引导用户用 WCH-LinkUtility。
- PS 输出按"最后一行是 JSON"提取（`ConvertTo-Json` 会把非 ASCII 转义成 `\uXXXX`，天然避开
  代码页问题）；PS 脚本文件要带 UTF-8 BOM 写入。
- 每次调用都要 1-3 秒 Add-Type 编译开销；这是 MRS2 同款架构的固有成本。
- 调用约定注意：MRVC 按 StdCall 声明且工作正常，但 MRS2 用 koffi 绑定（x86 上 cdecl 常见），
  怀疑崩溃时先用 dumpbin 核对导出符号的调用约定。

## 调试（gdb + OpenOCD server）

1. `openocd.exe -f wch-riscv.cfg`（gdb server 3333 / telnet 4444 / tcl 6666）
2. `<工具链>\bin\riscv-wch-elf-gdb.exe obj\<名>.elf` → `target extended-remote localhost:3333`
3. 断点符号名：入口是 `handle_reset`（.launch 的 stopAt），`set mem inaccessible-by-default off`、
   `set architecture riscv:rv32` 是常用客户端配置（见 .launch 的 gdbClientOtherCommands）。
4. 外设寄存器视图：芯片库 `<系列>xx.svd`。

## 下载失败速查

| 现象 | 原因/修复 |
|---|---|
| `no flash bank found for address 0x00000000` | hex 链接在 0 而 bank 基址非零：offset 要用 `A - H` 换算（见上） |
| 烧完校验失败/跑飞 | 双核工程用了单核 cfg；或擦除不完整（Erase All=true 才全片擦） |
| openocd 连不上（Failed to open WCH-Link） | 驱动/占用：WCH-LinkUtility 或别的 openocd 正占用设备；拔插重试 |
| cfg 报错 unknown command | 地址参数格式错（必须 `0x` 开头 hex）；或 wlink_set_address 放到了 init 之后 |
| 路径含中文烧录失败 | cfg 文件按 UTF-8 写了（应 ANSI），或路径用了反斜杠（应正斜杠） |
| 读保护后无法再连 | 先用 WCH-LinkUtility 解保护（解除会全片擦除，数据不保） |
