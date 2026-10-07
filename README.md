# mounriver-studio2-skill — MRS2（MounRiver Studio 2）工程操作 Skill

一个 [Agent Skills](https://agentskills.io) 开放标准格式的**知识库型**技能包，让 AI 编码客户端**不打开 MRS2 IDE** 就能发现、解析、修改、编译、烧录 WCH（南京沁恒）MRS2 工程。适用于 ZCode、Claude Code、Codex、Cursor、OpenCode 等支持 SKILL.md 的客户端。

skill 以文档为主体：工程文件格式、编译 flags 组装规则、OpenOCD 烧录语义（WCH 双重地址）都写成 AI 可直接执行的权威指南；工具链 / make / OpenOCD 直接复用本机 MRS2 安装目录里的原版程序。附带的命令行脚本只做轻量辅助（工程发现、配置摘要、芯片库查询），刻意不重复实现构建/烧录引擎——那部分的完整实现是 MRS2 IDE 与 [MRVC 插件](https://github.com/smartmx/MRVC)。

## 能做什么

- **知识库**：Eclipse CDT 工程文件（`.project` / `.cproject` / `.wvproj` / `.wvsln` / `.template` / `.launch`）的格式详解、superClass 对照表、编译排除语法、宏与链接路径解析规则、编码铁律
- **编译指南**：复用 obj/ 已生成的 makefile，或按配方手动组装 gcc 命令（GCC8 / GCC12 / GCC15 工具链取自 MRS2 安装目录）
- **烧录/调试指南**：手写 OpenOCD cfg（WCH-Link 双重地址语义、全片擦除、读保护、双核工程）
- **辅助脚本**：工程/solution 递归发现、工程配置摘要（flags/包含/宏/排除/下载信息）、芯片库查询
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

- **Windows**（工具链探测逻辑按 Windows 布局编写）
- **本机已安装 MounRiver Studio 2**——工具链、make、OpenOCD 均复用其安装组件，本 skill 不内置任何二进制。默认探测 `C:\MounRiver\MounRiver_Studio2`，也可用 `--mrs2 <路径>` 参数或 `MRS2_HOME` 环境变量指定
- **Python 3.8+**（纯标准库，无第三方依赖）

## 快速上手

安装后，AI 客户端在涉及 MRS2 工程的任务时会自动加载本 skill；也可直接调用其命令行工具：

```bash
python <skill目录>/scripts/mrs2.py find <目录>          # 递归发现工程/solution
python <skill目录>/scripts/mrs2.py show <工程目录>       # 解析工程配置摘要
python <skill目录>/scripts/mrs2.py toolchain             # 列出可用工具链
python <skill目录>/scripts/mrs2.py chips --series CH32V307  # 查芯片库
# 编译 / 烧录：按 references/build.md、references/flash-debug.md 的指南手动操作
```

## 目录结构

```
├── SKILL.md                  # 技能入口：触发条件、决策表、铁律
├── references/               # 按需加载的深入文档
│   ├── project-formats.md    #   工程文件格式与 superClass 对照表
│   ├── install-layout.md     #   MRS2 安装目录结构与工具链定位
│   ├── build.md              #   无 IDE 编译指南（makefile 复用 / 手动组装配方）
│   ├── flash-debug.md        #   烧录 / 调试 / 读保护
│   └── gotchas.md            #   常见报错与坑（路径、编码等）
└── scripts/
    └── mrs2.py               # 命令行工具（纯标准库）
```

## License

[MIT](LICENSE)
