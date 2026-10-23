# MRS2/MRS3 工程文件格式详解

六个文件构成一个工程：`.wvproj`（标记）+ `.project`（身份/链接资源）+ `.cproject`（构建配置）
+ `.template`（下载配置）+ `.launch`（调试）+ 可选 `.wvsln`（编组）。以下全部取自真实文件，
格式两代通用（MRS3 用同一套格式打开/构建 MRS2 EVT 工程）。

## .wvproj — 工程标记（空文件）

内容为空，仅文件名 `<工程名>.wvproj` 有意义；IDE 打开时重建内容。改名 = 删旧文件写新空文件。
发现工程时优先以它为标记，`.project` 兜底。

## .project — Eclipse 工程描述（UTF-8 XML）

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<projectDescription>
  <name>CH32V307VCT6</name>          <!-- 显示名；与文件夹名、.wvproj 名、.cproject ${ProjName} 联动 -->
  <comment/>                          <!-- 空元素两种写法同一文件里并存：<comment> 自闭合， -->
  <projects>
  </projects>                         <!-- <projects>/<arguments> 却写成跨行开闭对（真实文件如此） -->
  <buildSpec>
    <buildCommand>
      <name>org.eclipse.cdt.managedbuilder.core.genmakebuilder</name>
      <triggers>clean,full,incremental,</triggers>
      <arguments>
      </arguments>
    </buildCommand>
    <buildCommand>
      <name>org.eclipse.cdt.managedbuilder.core.ScannerConfigBuilder</name>
      <triggers>full,incremental,</triggers>
      <arguments>
      </arguments>
    </buildCommand>
  </buildSpec>
  <natures>
    <nature>org.eclipse.cdt.core.cnature</nature>            <!-- C 工程必有 -->
    <nature>org.eclipse.cdt.core.ccnature</nature>           <!-- C++ 工程才有；切换 C/C++ = 增删它 -->
    <nature>org.eclipse.cdt.managedbuilder.core.managedBuildNature</nature>
    <nature>org.eclipse.cdt.managedbuilder.core.ScannerConfigNature</nature>
  </natures>
  <filteredResources>...</filteredResources>  <!-- IDE 视图过滤，如隐藏 *.wvproj；可忽略 -->
</projectDescription>
```

- **C++ nature 的真 ID 是 `org.eclipse.cdt.core.ccnature`**——MRS2 自己的判定代码（`getEclipseProperties`）
  就按它工作：其自带扩展 bundle（`extensions\mrs-team.mrs-vscode\out\extension.js`）里只有
  `cnature` / `ccnature` 两个串，**`cxxnature` 从头到尾不存在**（CDT 也没有这个 ID）。见到
  `cxxnature` 的工程是被 bug 版工具写坏的：MRS2 视其为 C 工程、`.cpp` 源文件整体不参与编译。
  修复 = 换成 `ccnature` 并补 cpp 选项集（见下「C++ 工程在 .cproject 里的三件套」）。
- **空元素写法保真**：MRS2 把空元素写成自闭合（`<comment/>`）与跨行开闭对
  （`<projects>\r\n\t</projects>`）两种形态、同一文件里并存（真实文件如此），另有极少数工程用
  ` />`（斜杠前带空格）的自闭合变体。程序化写回 .project/.cproject 必须**记住每个元素的源
  形态并按原样输出**——统一规范成 `<x/>` 会在一次无关写入里顺带重写文件里每一处这种写法
  （真实 EVT 普查：2,687 个 .project 中 1,485 个含开闭对写法，示例文件 1,067 → 1,022 字节）。只有
  "原本有子元素、被编辑清空"的元素才落到 `<x/>` 形式。

### linkedResources（外部链接文件夹）

```xml
<linkedResources>
  <link>
    <name>StdPeriphDriver</name>                       <!-- 工程内显示名 -->
    <type>2</type>                                     <!-- 2 = 文件夹 -->
    <locationURI>PARENT-2-PROJECT_LOC/EXAM/PUB/StdPeriphDriver</locationURI>
  </link>
</linkedResources>
```

- `PARENT-N-PROJECT_LOC`：从 `PROJECT_LOC`（= 工程目录）向上 N 级再接尾段。EVT 树靠它共享
  `PUB` 目录。MRS1 老工程写 `<location>绝对或相对路径</location>`，MRS2 打开时自动转成
  `<locationURI>`。
- **打包残留坑**：EVT 发布包里常见机器绝对路径（如 `E:/.../EXAM/SRC`）。修复规则 =
  「最近祖先 + 尾段」：从工程目录逐级向上找第一个含有该尾段的祖先，改写成 `PARENT-N-PROJECT_LOC` 形式。

### 工程改名级联（做 Rename 必须全改，顺序无关但缺一不可）

1. `.project` 的 `<name>`
2. `.wvproj` 文件名
3. `.launch`：`org.eclipse.cdt.launch.PROGRAM_NAME`（`obj\<新名>.elf`）、
   `org.eclipse.cdt.launch.PROJECT_ATTR`、`MAPPED_RESOURCE_PATHS` 里的 `/旧名`
4. `.template`：`Target Path=obj/<新名>.hex`
5. `.wvsln`（若被编组）：`BuildOrder=` 行与成员路径
6. 文件夹本身**不重命名**（MRS2 同款行为：只改显示名）

## .cproject — 构建配置（CDT XML，编译唯一真相）

结构：`cconfiguration`（其 `name` 属性 = **构建目录名**，几乎都是 `obj`）→ `storageModule
cdtBuildSystem` → `configuration` → `toolChain` → 一串 `option` + 各 `tool`（assembler /
c.compiler / cpp.compiler / c.linker / cpp.linker / archiver / createflash / createlisting /
printsize）→ `sourceEntries`。

**选项以 superClass 的尾段为键**。读法：遍历 `<option>`，取 `superClass` 属性最后一个 `.`
之后的尾段对照下表；值看 `valueType`（`boolean`/`string`/`enumerated`/`includePath`/
`definedSymbols`/`stringList`/`libPaths`/`libs`/`userObjs`），列表值在子元素
`<listOptionValue value="..."/>`（常含 `&quot;` 包裹的 `${workspace_loc:...}` 宏）。

### superClass 尾段 → 含义 → 编译旗标

| superClass 尾段 | 含义 / 取值 |
|---|---|
| `option.command.prefix` | 工具链 prefix（`riscv-none-embed-` / `riscv-wch-elf-`）；大规模普查（2,685 个 .cproject、2,919 个前缀选项）**全部是裸形态**，语言限定形态 `c.command.prefix`/`cpp.command.prefix` 未实际出现（读取按"本语言 → 裸 → 另一语言"兼容即可） |
| `option.target.isa.base` | 枚举 `option.target.arch.rv32i` 等 → `-march` 基座 |
| `option.target.isa.multiply/compressed/atomic` | M/C/A 扩展开关 |
| `option.target.isa.xw` | WCH XW 扩展（`-march=rv32imacxw` 的 xw） |
| `option.target.isa.rvb / zmmul`（GCC12+） | `_zba_zbb_zbc_zbs` / `_zmmul` |
| `option.target.abi.integer` | 枚举 `option.abi.integer.ilp32`（/ilp32f/ilp32d）→ `-mabi` |
| `option.target.saverestore` | `-msave-restore` / `-mno-save-restore` |
| `option.target.other` | 逐字追加的自定义 target 旗标 |
| `option.optimization.level` | 枚举尾段：`none`→-O0 `optimize`→-O1 `more`→-O2 `most`→-O3 `fast`→-Ofast `debug`→-Og `z`→-Oz **其余/缺省→-Os** |
| `option.optimization.messagelength/signedchar/functionsections/datasections/nocommon/noinlinefunctions/freestanding/nobuiltin/spconstant/PIC/lto/nomoveloopinvariants` | 对应 `-f...` 开关 |
| `option.optimization.mrs.highcode/asmsoftlib/pipe/caret` | WCH 专属：`--param=highcode-gen-section-name=1` / `-Xassembler -wchsoftlib` / `-pipe` / `-fno-diagnostics-show-caret` |
| `option.warnings.allwarn/extrawarn/unused/uninitialized/toerrors/pedantic/conversion/shadow/...` | `-Wall` `-Wextra` `-Wunused` `-Wuninitialized` `-Werror` `-pedantic` `-Wconversion` `-Wshadow` 等 17 项，逐一对应 |
| `option.debugging.level` | `none`→无 -g `minimal`→-g1 `max`→-g3 其余→-g |
| `option.debugging.format` | `gdb`→-ggdb `dwarf2..5`→-gdwarf-N |
| `option.assembler.usepreprocessor` | true → 汇编行加 `-x assembler-with-cpp` |
| `option.assembler.include.paths` / `option.c.compiler.include.paths` / `option.cpp.compiler.include.paths` | `-I"<解析后的路径>"` 列表 |
| `option.c.compiler.defs` / `option.cpp.compiler.defs` | `-D<宏>` 列表（值里可含字面引号） |
| `option.c.compiler.std` | 枚举 `...std.gnu99` → `-std=gnu99`（gnu11/gnu17 同理） |
| `option.c.linker.scriptfile` / `cpp.linker.scriptfile` | `-T"<链接脚本>"` 列表 |
| `option.c.linker.gcsections` | `-Xlinker --gc-sections` |
| `option.c.linker.nostart` | `-nostartfiles` |
| `option.c.linker.usenewlibnano` / `usenewlibnosys` | `--specs=nano.specs` / `--specs=nosys.specs` |
| `option.c.linker.paths` / `libs` / `otherobjs` / `flags` | `-L` / `-l` / 额外 .o / `-Xlinker <项>` |
| `option.addtools.createflash / createlisting / printsize` | 构建后生成 hex / 扩展反汇编 / size 报告 |
| `option.createlisting.*` | objdump 参数（disassemble/demangle/allheaders…） |
| `option.printsize.format` | 枚举（berkeley 等） |

WCH 专属库（`option.c.linker.libs` 里出现）：`-lprintf`（SPI printf）、`-lprintfloat`、
`-lIQmath_RV32`。`configuration` 的 `artifactName` 几乎都是 `${ProjName}`；
`buildArtefactType.exe` = 可执行，`...buildArtefactType.staticLibrary` = 静态库。

### C++ 工程在 .cproject 里的三件套（C↔C++ 互转时逐项对齐，缺一构建即坏）

1. `.project` 的 `org.eclipse.cdt.core.ccnature` nature（见上）。
2. **cpp.* 选项集与 c.* 孪生并存**。原生 C++ 工程的两套值**本就不同**（952 个实采 C++ 工程
   全部如此：包含路径、std、picolibc、defs 各自独立），不要"顺手同步"它们。但从 C 转 C++ 必须把
   C 选项**整组镜像**进 cpp 集——C 工程的 cpp.* 几乎是空的，只改 nature 会得到"空 C++ 配置"：
   链接拿不到 `-T` 脚本，报 `cannot open linker script file Link.ld`（脚本名回退成裸文件名）。
   切回 C 时镜像值可保留（nature=C 时被忽略），但转换新增的 `<inputType>` 要删掉。
3. **C++ 编译器的 `<inputType>`**：C++ 工程在 `GNU RISC-V Cross C++ Compiler` tool 下带
   `<inputType id="ilg.gnumcueclipse.managedbuild.cross.riscv.tool.cpp.compiler.input.1079228323"
   superClass="ilg.gnumcueclipse.managedbuild.cross.riscv.tool.cpp.compiler.input"/>`——MRS2
   自家 C++ 模板用的就是这个固定 id；C 工程只有 assembler / c.compiler / c.linker 三个 inputType。

**值写法保真**：`libraries` / `defined_symbols` 进 MRS2 模型是**原样**的（读侧只有路径类字段
经 `EPMacroStrResolve` 剥引号）——库名 `m` 不要改写成 `"m"`，引号会被带进 MRS2 模型与
`USER_OBJS`（MRS2 还会再补一层引号）；程序化复制列表值时**逐属性原样克隆**，不要经
"剥引号→统一加引号"往返。

### sourceEntries — 参与编译的源码范围与排除（两种并存风格）

```xml
<sourceEntries>
  <!-- 根 entry：excluding 列表（| 分隔）= 交给各自 entry 的目录 + 真正排除的文件 -->
  <entry excluding="Startup|Peripheral|Ld|Debug|Core" flags="VALUE_WORKSPACE_PATH|RESOLVED" kind="sourcePath" name=""/>
  <!-- 命名 entry：该目录整体参与编译 -->
  <entry flags="VALUE_WORKSPACE_PATH|RESOLVED" kind="sourcePath" name="Core"/>
  <!-- 命名目录里再排除部分文件（注意 CH58x 的 StdPeriphDriver 常这样裁外设驱动） -->
  <entry excluding="CH59x_pwm.c|CH59x_spi0.c|..." flags="VALUE_WORKSPACE_PATH|RESOLVED" kind="sourcePath" name="StdPeriphDriver"/>
</sourceEntries>
```

语义（与 CDT/MRS2 一致）：
- 扫描范围 = 全工程 ∪ 各命名 entry 目录 − 根 entry `excluding` − 各命名 entry 自己的 `excluding`。
- 根 entry `excluding` 里的**裸目录名同时是标记**（表示"该目录有自己的 entry"，防止双扫）。
- excluding 里的 token 是**工程根相对路径**（`/` 分隔）：含 `/` 的 token 匹配该前缀（文件或目录）；
  裸 token 匹配直接子项。排除目录 = 排除其下全部内容。
- 在树上"排除一个文件"：把其工程根相对路径追加到所属 entry（命名 entry 命中时加到那个 entry，
  否则加到根 entry；根 entry 缺失则先创建空 name 的根 entry）。

## .template — 下载配置（Java properties 文本，非 XML）

```
Mcu Type=CH32V30x
Target Path=obj/CH32V307VCT6.hex        # 烧录目标（相对工程根）
Address=0x08000000                      # 下载地址（缺省时按芯片推断）
Erase All=true                          # 下载前全片擦除（双核 = 2 bank）
Program=true
Verify=true
Reset=true

Vendor=WCH
Link=WCH-Link
Toolchain=RISC-V
Series=CH32V307
RTOS=NoneOS
MCU=CH32V307VCT6
Description=Website: ...                # 可含 \n 转义与中文
PeripheralVersion=3.1
TempratureScope=CH32V307VCT6{-40℃~85℃}
```

要点：键值 `K=V`、空行分节、支持中文（文件按 ANSI/GBK 或 UTF-8 都可能遇到，读时双编码尝试）；
`Address` 格式严格 `0x` + 1-8 位十六进制。烧录引擎语义见 flash-debug.md。

## .launch — 调试配置（Eclipse XML）

关键属性（其余可忽略）：

```
com.mounriver.debug.gdbjtag.openocd.gdbServerExecutable = ${eclipse_home}toolchain/OpenOCD/bin/${openocd_executable}   ← MRS1 老路径，MRS2 实际用 resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin
com.mounriver.debug.gdbjtag.openocd.gdbServerOther      = -f "wch-riscv.cfg"
com.mounriver.debug.gdbjtag.openocd.gdbServerGdbPortNumber = 3333
org.eclipse.cdt.dsf.gdb.DEBUG_NAME                      = <工具链>\bin\riscv-none-embed-gdb.exe
org.eclipse.cdt.launch.PROGRAM_NAME                     = obj\CH32V307VCT6.elf
org.eclipse.cdt.debug.gdbjtag.core.stopAt               = handle_reset
```

## .wvsln — solution（纯文本，行式）

```
-arm:${eclipse_home}\toolchain\arm-none-eabi-gcc\bin     ← 5 行工具链配置，可忽略/跳过
-build:${eclipse_home}\toolchain\Build Tools\bin
-openocd name:openocd.exe
-openocd path:${eclipse_home}\toolchain\OpenOCD\bin
-rv:${eclipse_home}\toolchain\RISC-V Embedded GCC\bin
BuildOrder=LED,USART,Timer                                ← 按工程显示名排构建顺序（缺省按行序）
..\LED\LED.wvproj                                         ← 成员路径：相对 .wvsln 所在目录
..\EXAM\USART\USART.wvproj                                ← 也可绝对路径；/ 或 \ 均可
```

解析规则（MRS2 宽松语法）：`-key:value` 开头的行是工具链配置；`BuildOrder=` 一行；
其余非空行都是成员（相对路径基于 `.wvsln` **文件所在目录**解析，所以自写时成员行必须以
`..\` 开头才指到兄弟目录）。容忍陈旧绝对路径与重复成员：解析时去重（Windows 大小写不敏感）、
标记不存在的路径。

## 宏与路径

- `${ProjName}` → `.project` 的 `<name>`。
- `${workspace_loc:/${ProjName}/X}` → **本工程目录**下 `X`（.cproject 里 99% 都是这种形式）。
- `${workspace_loc:/OtherProject/X}` → Eclipse 语义是工作区根下，MRS2/MRVC 均按工程根处理
  （坑：多工程 solution 中会指错，见 gotchas.md）。
- `${eclipse_home}` → MRS1 安装根（MRS2 时代视为遗留，跳过）。
- 列表项常带字面引号（`&quot;${workspace_loc:...}&quot;`），取值时剥引号。
