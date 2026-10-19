# MRS2 构建原理与无 IDE 编译

## MRS2 怎么构建（理解原理才能排错）

MRS2/CDT 的 managed build：**首次构建时**根据 `.cproject` 在构建目录（配置名，即 `obj/`）生成
CDT 风格 makefile（`makefile` / `sources.mk` / `objects.mk` / `<子目录>/subdir.mk`），之后执行
`make -jN all`（make 用 MRS2 自带的 `others\Build_Tools\Make\bin\make.exe`）。所以：

- obj/ 里出现 makefile 是正常产物；手工改它们会在下次重新生成时被覆盖。
- 配置改变后 IDE 会重新生成 makefile——命令行复现构建时要么照抄生成规则，要么绕开 makefile
  直接调工具链（见下"直接编译配方"）。
- **优先复用已有 makefile**：工程构建过一次后（MRS2/MRVC 构建过），obj/ 里有完整 makefile 集合，
  增量/全量构建直接 `make -C obj -jN all`（make 用
  `$MRS2\...\others\Build_Tools\Make\bin\make.exe`），不必重新推导 flags。只有从未构建过、
  或刚改过 `.cproject` 时才需要手动组装命令。
- makefile 里的路径按**系统 ANSI 代码页**写盘（zh-CN = GBK）；配方里的字面 `$` 必须写成 `$$`
  （make 先展开 `$` 序列再交给 shell；但 make 自动变量 `$@ $< $^ $* $?` 与用户写的 `$(VAR)`
  不得转义——`-Wa,-adhlns="$@.lst"` 被写成 `$$@` 后 shell 看到空值，清单静默失效）。
  路径字符能否编译要分层判定（make 规则词 / 引号参数 / 无引号展开三层），实测矩阵见下节。

## 路径字符与 recipe 执行 shell（逐字符实测矩阵）

**recipe 走 sh，不走 cmd.exe**：MRS2 的 make bundle（`others\Build_Tools\Make\bin\`：make.exe +
sh.exe + rm/mkdir/echo/busybox）里，Windows 版 GNU make 在 PATH 上找到 sh.exe 时用 **sh 执行
recipe**（找不到才退回 cmd.exe）。命令行复现构建时把 `工具链\bin; Make\bin; %PATH%` 注入
PATH 即复刻 MRS2/MRVC 构建环境。判定路径字符时，判的是"make 规则词 + sh 展开"两层，不是
cmd 语义。

**make 规则词（target/prereq）字符语义**：

- `;` 在规则词中开启行内 recipe、`#` 开启注释——规则词内**均不可转义**；
- `%` 在非模式规则的规则词中是**字面量**（只有模式规则里才是通配符）；
- `[` 在 prereq 中触发 glob，但**匹配不到文件时保持字面量**——随工程根出现通常无害；作为
  USER_OBJS 这类恰好能匹配别处的独立词才致命（`[12]` 静默 glob 到别的目录链错对象）；
- `&` `(` `)` `'` 对 make 层无害，问题只在 sh **无引号展开**层。

**实测矩阵**（真实 CH592 FreeRTOS 带链接工程逐字符复制改名 + MRS2 自带 make 实编，六轮
对抗性评审定版；MRVC 0.2.1 按此实现并带永久回归）：

| 位置 | 支持 | 拒绝 |
|---|---|---|
| 工程根（含链接目录的工程） | `% ( ) & @ ! , ~ '` | `;` `#` 反引号 |
| 工程根（无链接目录工程） | 上述全部，另加 `;` `#` | 反引号 |
| Other Objects（USER_OBJS） | — | `;` `#` 反引号 `& ( ) '` `[ ]` |
| 库名（LIBS） | 仅 `A-Za-z0-9._+-` | 其余全部 |
| 源文件名 | — | `( ) ; #` 反引号（EVT 全系无此命名，不在支持范围） |

原理：工程根字符只出现在**相对 prereq** 和**引号包裹的绝对旗标参数**（`-I"path"`/`-T"path"`）
里，永远不进规则词——所以 `(` `)` `;` `#` 都能活（EVT 发布目录带括号如
`CH592EVT_V1.9_(20261016)` 是合法可编译的）。链接目录的文件规则用**绝对路径 prereq**（MRS2
同款），根路径字符随之进规则词——`;` `#` 在此不可表达，MRS2 自己也构建失败，且其生成器会把
根路径里的 `#` **误改写成 `%`** 产出错误路径。**反引号是唯一全通道拒绝的字符**：sh 在双引号
内仍做命令替换（报 `EOF in backquote substitution`），连引号包裹的 include 路径里带一个反引号
都救不了，库名/旗标/文件名/Build Steps 任何通道出现都要拒绝。

**cmd.exe 包装层**（自己写 .cmd 调 make 时）：`%` 要写成 `%%`；`!` 只在**延迟展开关闭**时安全
——父环境经注册表 AutoRun 或 `cmd /v:on` 开启延迟展开会吞掉路径里的 `!`，.cmd 首行
`setlocal DisableDelayedExpansion` 兜底；.cmd 文件按系统 ANSI 码页解析（含中文用户名的机器，
`%TEMP%` 记录文件路径非 ASCII）。构建日志看不出实际命令行时用 `make -n -B all` 干跑——
MRS2/MRVC 的 recipe 带 `@` 静默，干跑打印全部实际命令（链接/objcopy/size 全覆盖）。

## 直接编译配方（与 MRS2 等价的命令行）

单文件编译（C 源，RISC-V）：

```
<工具链>\bin\riscv-wch-elf-gcc -march=rv32imacxw -mabi=ilp32 -msmall-data-limit=8
  -msave-restore -fmax-errors=20            ← MRS2 2.x 风格固定加
  -Os -fmessage-length=0 -fsigned-char -ffunction-sections -fdata-sections -fno-common
  [-std=gnu99] [-Wall ...] [-g]
  -I<工程>\Debug -I<工程>\Core ...           ← .cproject include.paths，宏已解析
  [-D宏...]
  -c User/main.c -o obj/User/main.o
```

汇编源（.S）：同上，另加 `-x assembler-with-cpp`（当 `assembler.usepreprocessor=true`，MRS2
模板默认 true），include 用 `assembler.include.paths`。

链接：

```
riscv-wch-elf-gcc -march=... -mabi=...
  -T Ld/Link.ld -nostartfiles --specs=nano.specs --specs=nosys.specs
  -Xlinker --gc-sections
  obj/***.o          ← 全部目标文件
  [-L<路径>] [-l<库>...] [额外.o]
  -lm
  -o obj/<工程名>.elf
```

产物（按 addtools 开关）：`objcopy -O ihex <elf> obj/<名>.hex`、`objcopy -O binary <elf>
obj/<名>.bin`、`objdump -d -C -x <elf> > obj/<名>.lst`、`size <elf>`（Berkeley 格式）。

### -march 组装规则（按序拼接）

基座（`isa.base` 枚举，如 `rv32i`）→ `m`（multiply）→ `a`（atomic）→ 浮点后缀（fpAbi=single
加 `f`，double 加 `fd`）→ `c`（compressed）→ XW 扩展：
- GCC8：直接接 `xw` → `rv32imacxw`
- GCC12/GCC15：接 `_xw`；且 `rvb` → `_zba_zbb_zbc_zbs`、`zmmul` → `_zmmul`

`-mabi` = integerAbi（`ilp32`/`ilp32f`/`ilp32d`）+ 浮点后缀同上。
其余 target 旗标（`readTargetProcessor` 语义）：`-mtune=<tuning>`（default 省略）、
`-mcmodel=med<any>`（code_model 非 default 时）、`-msmall-data-limit=<N>`（默认 8）、
`-mstrict-align`/`-mno-strict-align`（align=strict/nostrict）、`-msave-restore`（模板默认 true）。

### 宏解析

`-I`/`-L`/`-T` 项的取值：剥字面引号 → `${workspace_loc:/${ProjName}/X}` → `<工程根>/X` →
转正斜杠、盘符小写（MRS2 2.x 风格）→ **目录不存在则丢弃该 -I**（MRS 同款行为，FreeRTOS
工程少一条 -I 是正常的）。`-D` 值原样保留（可能含字面引号，如 `-DSTR="abc"`）。

## 与 MRS2 输出的差异（何时必须用 IDE 产物）

手动组装的目标是"命令行可复现、产物可烧录"，与 CDT makefile 的差异：

| 项 | CDT/MRS2 | 手动组装 |
|---|---|---|
| 目标文件布局 | obj/<子目录>/<名>.o，同名 .c 靠 CDT 去重 | 自定（建议 obj/<相对路径>.o，天然无同名冲突） |
| 字节级 makefile | 逐字节复刻 1.9.2/2.1.0 金标 | 不经 makefile |
| 预定义宏继承 | 无（模板不加 -D） | 同 MRS2（读 .cproject defs） |
| .cpp / C++ 工程 | cxx nature 驱动 | 同（.cproject 有 cpp 段则启用） |

需要与 IDE 字节一致（比如比对行为差异）时，用 MRS2 IDE 或 MRVC 插件构建，不要混用两套
产物目录（先 clean 再切工具）。`show --json` 输出的 flags 是组装参考，但其对 CDT 语义的
覆盖是精简版——复杂工程（FPU/特殊宏/多配置）以 MRS2/MRVC 产物为准。

## 静态栈/调用分析（MRS2 闭源功能的开源替代）

编译时追加 `-fstack-usage`（每个 .c 旁生成 .su：函数栈用量）与
`-fdump-rtl-expand -fdump-rtl-expand=<路径>`（RTL dump，调用图数据源）。

- **RTL dump 函数头真实格式**：`;; Function main (main, funcid=1)`——解析 caller 名必须截断
  括号部分（只取 `;; Function ` 到首个 `(` 之前），否则拿到 `main (main, funcid=1)`。
- call 行里被调者取 `symbol_ref("名字")` 的第一个引号串；函数指针调用行没有 symbol_ref、
  行尾带 `"文件名":行:列` 位置串，需要排除。
- 汇编清单开关（`asmlisting` 类选项）生成 `-Wa,-adhlns="$@.lst"`——其中 `$@` 是 **make 自动
  变量**，只在 CDT makefile 里有效；自己做构建时直接写 `-Wa,-adhlns=obj/xx.lst`。

## 常见构建失败速查

| 现象 | 原因 |
|---|---|
| `riscv-none-embed-gcc: not found` | .cproject prefix 与所选工具链代际不符（GCC8=riscv-none-embed-，GCC12=riscv-wch-elf-，GCC15=riscv32-wch-elf-） |
| `No rule to make target` | 链接工程根/链接目录含 `;` `#`（绝对 prereq 进规则词，MRS2 同败且把 `#` 误写成 `%`）；或源文件名含 `(` `)` `;` `#` 或空格（规则词层无法表达）。工程根本身含 `( ) ; % #` 不是原因 |
| 链接 undefined reference 到外设函数 | 该外设 .c 被 StdPeriphDriver entry 的 excluding 裁掉了（CH58x 常见，属预期裁剪） |
| include 找不到 | `${workspace_loc:/其他工程/...}` 指错根；或 include 目录不存在被静默丢弃 |
| 中文路径乱码/打不开文件 | 构建脚本按错误编码写盘（应 ANSI/GBK）；OpenOCD cfg 里应正斜杠 |
| makefile 里 `$@` 变成 `$$@` | 把 make 自动变量也做了 `$`→`$$` 转义（只应转义用户路径里的 $） |
