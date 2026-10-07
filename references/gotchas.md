# MRS2 工程坑清单（排错时读）

按"现象 → 根因 → 处置"组织。这些坑全部来自对 MRS2 真实工程（EVT 树、SDK 模板、MRS1 遗留）
的处理经验。

## 编码与文件读写

- **双编码现实**：`.project`/`.cproject`/`.launch` 声明 UTF-8，但含中文工程名的 `.template`、
  `.wvsln`、makefile 可能是 ANSI/GBK。读文件：先 UTF-8 试解码，失败回退 GBK（`cp936`）。
  写 `.template`/cfg/makefile：一律系统 ANSI（`locale.getpreferredencoding(False)`，zh-CN 即
  GBK/`mbcs`）。UTF-8 写入中文路径的 cfg 会让 OpenOCD 的 Jim Tcl 打不开文件。
- XML 转义：写回 `.cproject`/`.project` 时 `&`→`&amp;`（先做）、`<`→`&lt;`、属性内 `"`→`&quot;`。
  列表值里的宏形如 `&quot;${workspace_loc:...}&quot;`——取值剥引号，写回补引号。
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

- makefile 域的敌对字符：`(` `)` `;` `#` `%` 无法在任何 makefile 位置表达；`$` 需 `$$`；
  空格需引号或显式规则。工程根与链接根可以预检，**树内的文件名也要检**（`main(1).c` 这类
  下载解压产物是常客）。
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

## 已知失败模式（现象速查）

| 现象 | 第一排查点 |
|---|---|
| 构建成功但 .lst/栈分析产物没生成 | `$@` 被过度转义（makefile 域）或分析 dump 头解析没截断 `(..., funcid=N)` |
| 烧录"成功"但芯片没反应 | hex 双重地址换算错；或擦的是 bank 0、代码在 bank 1（双核） |
| 排除文件后仍被编译 | 根 entry 裸名标记语义 / 命名 entry 未改写 |
| 打开 MRS2 后工程属性空白/报错 | .cproject XML 转义或结构被破坏——用备份恢复后按 superClass 表重新改 |
| 中文日志乱码 | 控制台按 GBK 解码了 UTF-8 输出（或反之）；工具链输出按 ANSI 处理 |
| `C:` 盘符路径跑到别处 | `path.resolve("C:")` 解析到该盘当前目录；盘符根必须写成 `C:\` |
