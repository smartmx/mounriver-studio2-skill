# mounriver-studio2-skill — MRS2/MRS3（MounRiver Studio 2/3）工程操作 Skill

一个 [Agent Skills](https://agentskills.io) 开放标准格式的**知识库型**技能包，让 AI 编码客户端**不打开 MounRiver Studio IDE** 就能发现、解析、修改、编译、烧录 WCH（南京沁恒）MRS2/MRS3 工程。适用于 ZCode、Claude Code、Codex、Cursor、OpenCode 等支持 SKILL.md 的客户端。

skill 以文档为主体：工程文件格式、编译 flags 组装规则、OpenOCD 烧录语义（WCH 双重地址）都写成 AI 可直接执行的权威指南；两代 IDE 目录结构同构，工具链 / make / OpenOCD 直接复用用户提供的 MounRiver 安装目录（MRS2 或 MRS3）里的原版程序。**支持 Windows / Linux / macOS**：Windows 上 MRS2/MRS3 都是完整 IDE；Linux/macOS 上 MRS2 代官方包只有纯工具链，完整 IDE 用 MRS3（详见 `references/install-layout.md`）。附带的命令行脚本只做轻量辅助（安装定位、工程发现、配置摘要、芯片库查询、路径字符可构建性警告），刻意不重复实现构建/烧录引擎——那部分的完整实现是 MounRiver IDE 与 [MRVC 插件](https://github.com/smartmx/MRVC)。

## 能做什么

- **知识库**：Eclipse CDT 工程文件（`.project` / `.cproject` / `.wvproj` / `.wvsln` / `.template` / `.launch`）的格式详解、superClass 对照表、编译排除语法、宏与链接路径解析规则、编码铁律、MRS2/MRS3 代次判定、三平台目录布局与架构门禁
- **编译指南**：复用 obj/ 已生成的 makefile，或按配方手动组装 gcc 命令（GCC8 / GCC12 / GCC15 工具链取自 MounRiver 安装目录，两代前缀一致）；Windows 用 cmd/make bundle，Linux/macOS 用 `sh` + 自带/系统 make
- **烧录/调试指南**：手写 OpenOCD cfg（WCH-Link 双重地址语义、全片擦除、读保护、双核工程）；wlink 底层库三平台同名（Windows `McuCompilerDll.dll` P/Invoke，Linux/macOS `libmcuupdate.so/.dylib` 进程内 FFI），Linux/macOS 的 OpenOCD 路径、udev 规则与实测边界
- **辅助脚本**：安装定位（MRS2/MRS3 IDE 或纯工具链包，Windows/Linux/macOS）、工程/solution 递归发现、工程配置摘要（flags/包含/宏/排除/下载信息/路径字符可构建性警告）、芯片库查询
- **适用对象**：CH32 全系列（CH32V103 / V203 / V307 / H417 等）、CH56x / CH57x / CH58x / CH59x 等 RISC-V 与 ARM 内核 MCU 工程

## 安装

一键安装（自动识别本机已装的 AI 客户端）：

```bash
npx skills add smartmx/mounriver-studio2-skill
```

或手动 clone 到客户端的技能目录：

```bash
# ZCode（用户级，所有项目可用）
git clone https://github.com/smartmx/mounriver-studio2-skill.git ~/.zcode/skills/mounriver-studio2-skill

# ZCode（仅当前项目）
git clone https://github.com/smartmx/mounriver-studio2-skill.git <项目>/.zcode/skills/mounriver-studio2-skill

# Claude Code
git clone https://github.com/smartmx/mounriver-studio2-skill.git ~/.claude/skills/mounriver-studio2-skill
```

## 环境要求

- **Windows / Linux / macOS** 之一：
  - **Windows**：已安装 MRS2 或 MRS3 完整 IDE（其一即可）；
  - **Linux**：已安装 MRS3（.deb 实装 `/usr/share/MRS3/MRS-linux-x64`，或 tar.xz 解包），或解包 MRS2 代纯工具链包（无 IDE/SDK/自带 make）；
  - **macOS**：已安装 MRS3（`/Applications/MounRiver Studio 3.app`，arm64 专用），或解包 MRS2 代纯工具链包（包内 GCC8/ARM 为 x86_64、GCC12/15 为 arm64）。
- **安装路径来源按优先级**：`--mrs2 <安装根/工具链根>` 参数（MRS2/MRS3、IDE/纯工具链通用，自动识别代次与布局）→ `MRS2_HOME` / `MRS3_HOME` 环境变量 → 本机平台惯例位置（Windows `C:\MounRiver\MounRiver_Studio2` / `MounRiver_Studio3`；Linux `/usr/share/MRS3/MRS-linux-x64`；macOS `/Applications/MounRiver Studio 3.app`）。纯工具链包没有惯例位置，必须显式提供。都不存在时会提示"请先安装 MRS2/MRS3 或解包工具链包，并提供安装路径"
- **Python 3.8+**（纯标准库，无第三方依赖）
- **版本依据**：本 skill 结论实证于 MRS2 `2.0.0`（含 V240/2.4.0 纯工具链包）与 MRS3 `3.0.0`（三平台包）；其余/未来版本的结构与行为未验证——先按所属大版本（MRS2/MRS3）已知结构尝试，不通再按 SKILL.md 的判定标志实际探测所需组件

## 快速上手

安装后，AI 客户端在涉及 MRS2/MRS3 工程的任务时会自动加载本 skill；也可直接调用其命令行工具（`--mrs2 <安装根>` = MounRiver IDE 安装根或纯工具链根，可省略——按环境变量与本机平台惯例位置探测）：

```bash
python <skill目录>/scripts/mrs2.py find <目录>              # 递归发现工程/solution
python <skill目录>/scripts/mrs2.py show <工程目录>           # 解析工程配置摘要
python <skill目录>/scripts/mrs2.py --mrs2 <安装根> toolchain  # 列出可用工具链
python <skill目录>/scripts/mrs2.py --mrs2 <安装根> chips --series CH32V307  # 查芯片库（需 IDE）
# Linux/macOS 示例：--mrs2 /usr/share/MRS3/MRS-linux-x64
#                或 --mrs2 "/Applications/MounRiver Studio 3.app"
#                或 --mrs2 /opt/MRS_Toolchain_Linux_X64_V240（纯工具链包）
# 编译 / 烧录：按 references/build.md、references/flash-debug.md 的指南手动操作
```

## 目录结构

```
├── SKILL.md                  # 技能入口：触发条件、决策表、铁律
├── references/               # 按需加载的深入文档
│   ├── project-formats.md    #   工程文件格式与 superClass 对照表
│   ├── install-layout.md     #   MRS2/MRS3 安装目录结构、代次判定与工具链定位
│   ├── build.md              #   无 IDE 编译指南（makefile 复用 / 手动组装配方）
│   ├── flash-debug.md        #   烧录 / 调试 / 读保护
│   └── gotchas.md            #   常见报错与坑（路径、编码等）
└── scripts/
    └── mrs2.py               # 命令行工具（纯标准库）
```

## License

[MIT](LICENSE)
