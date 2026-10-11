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
  （make 先展开 `$` 序列再交给 shell）；`(` `)` `;` `#` `%` 在 makefile 路径里无法表达——
  工程/文件名含这些字符时 MRS2 自己也会产出坏 makefile（"No rule to make target"）。

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

## 静态分析 / IntelliSense（让编辑器不报假红）

MRS2 的实现（extension.js 源码级取证）：自带魔改 clangd（私有参数 `--enable-wch-ext`），
单 LSP 实例 + **每工程缓存 CDB**（`%TEMP%\mrs-cache\<工程名>-<md5>\compile_commands.json`），
切换工程上下文 = 杀进程重启换 `--compile-commands-dir`。**工程级 `-D` 宏隔离的唯一手段就是
每工程一份 CDB + 切目录**——`--query-driver` 只补工具链内建宏/include，补不了工程宏。

在 VSCode（MRS2 之外）复刻的正确架构：

1. 从 `.cproject` 生成该工程的 `compile_commands.json`：每个源文件一条
   `{directory: 工程根, command: 完整 gcc 命令行, file: 源文件路径}`，命令行按本文"直接编译配方"
   组装（-I 用解析后的绝对路径，-D 原样保留字面引号）。汇编 .S 文件也收录
   （`-x assembler-with-cpp`）。
2. **clangd** 路线：工程根放 `.clangd` 指定 `CompileFlags: CompilationDatabase: <路径>`，
   或启动参数 `--compile-commands-dir`；多工程 solution 各工程独立 CDB。
3. **cpptools** 路线：`c_cpp_properties.json` 的 `compileCommands` 指向 CDB，`configuration`
   按工程命名；一次只把"当前活动工程"的 CDB 放进配置即可（MRVC 同款语义：树选中工程 →
   切换活动数据库）。
4. 链接目录（linked folder）的源文件在 CDB 里按**物理路径**收录，否则编辑器从物理文件
   反查不到条目（与编译换算规则一致，见 scan_sources 语义）。

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
| `No rule to make target` | 文件/目录名含 `(` `)` `#` `%` `;` 或空格（CDT makefile 无法表达） |
| 链接 undefined reference 到外设函数 | 该外设 .c 被 StdPeriphDriver entry 的 excluding 裁掉了（CH58x 常见，属预期裁剪） |
| include 找不到 | `${workspace_loc:/其他工程/...}` 指错根；或 include 目录不存在被静默丢弃 |
| 中文路径乱码/打不开文件 | 构建脚本按错误编码写盘（应 ANSI/GBK）；OpenOCD cfg 里应正斜杠 |
| makefile 里 `$@` 变成 `$$@` | 把 make 自动变量也做了 `$`→`$$` 转义（只应转义用户路径里的 $） |
