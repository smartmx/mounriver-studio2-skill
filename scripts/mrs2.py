#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mrs2.py — MounRiver Studio 2 (MRS2) 工程命令行工具（无需 MRS2 IDE）。

子命令:
  find      递归发现 MRS2 工程 (.wvproj/.project) 与 solution (.wvsln)
  show      解析一个工程的全部配置并输出摘要
  toolchain 列出 MRS2 安装目录里的工具链 (sub_manifest.json)
  chips     扫描芯片库 (SDK/default) 的系列/型号/下载地址/能力
  sln       解析 .wvsln solution 文件
  build     直接调用工具链编译（等价 MRS2 managed build 的命令行复现）
  flash     OpenOCD + WCH-Link 烧录（含 WCH 双重地址语义）

环境: Windows + MRS2 安装目录（--mrs2 或 MRS2_HOME 或常见位置探测）。
Python 3.8+，仅标准库。工具链/OpenOCD 均来自 MRS2 安装目录。
"""
import argparse
import codecs
import json
import locale
import os
import re
import subprocess
import sys
import time

try:  # 防止 GBK 控制台打印中文/特殊字符时崩溃（不改变终端编码）
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass

SRC_C = {'.c'}
SRC_CPP = {'.cpp', '.cxx', '.cc'}
SRC_ASM = {'.s', '.S'}
HIDDEN_PREFIX = '.'
BUILD_DIR_NAMES = {'obj'}  # 配置名会在解析后补充；此处是兜底

ANSI = 'mbcs' if os.name == 'nt' else locale.getpreferredencoding(False)


# ---------------------------------------------------------------- encoding

def read_text(p):
    """读文本：BOM → UTF-8 → GBK 兜底（.template/.wvsln 中文现实）。"""
    with open(p, 'rb') as f:
        b = f.read()
    if b.startswith(codecs.BOM_UTF8):
        return b.decode('utf-8-sig')
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', errors='replace')


def write_ansi(p, s):
    """写 MRS2 域文件（.template/cfg/makefile）：系统 ANSI 代码页。"""
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    with open(p, 'w', encoding=ANSI, newline='') as f:
        f.write(s)


# ---------------------------------------------------------------- install

class Mrs2Install:
    def __init__(self, root, win32):
        self.root = root                       # 安装根，如 D:\MounRiver\MounRiver_Studio2
        self.win32 = win32
        wc = os.path.join(win32, 'components', 'WCH')
        self.toolchain_dir = os.path.join(wc, 'Toolchain')
        self.openocd_bin = os.path.join(wc, 'OpenOCD', 'OpenOCD', 'bin')
        self.sdk_dir = os.path.join(wc, 'SDK', 'default')
        self.wch_others = os.path.join(wc, 'Others')
        self.make_bin = os.path.join(win32, 'others', 'Build_Tools', 'Make', 'bin')

    def __str__(self):
        return self.win32


def find_install(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get('MRS2_HOME'):
        cands.append(os.environ['MRS2_HOME'])
    cands += [r'C:\MounRiver\MounRiver_Studio2', r'D:\MounRiver\MounRiver_Studio2',
              r'C:\MounRiver\MounRiver Studio 2', r'D:\MounRiver\MounRiver Studio 2']
    marker_rel = os.path.join('resources', 'app', 'resources', 'win32', 'components', 'WCH', 'manifest.json')
    for c in cands:
        c = c.strip().strip('"')
        if os.path.isfile(os.path.join(c, *marker_rel.split(os.sep))):
            return Mrs2Install(c, os.path.join(c, 'resources', 'app', 'resources', 'win32'))
        # 允许直接填到 .../win32 这一层
        if os.path.isfile(os.path.join(c, 'components', 'WCH', 'manifest.json')):
            root = c
            for _ in range(3):
                root = os.path.dirname(root)
            return Mrs2Install(root, c)
    raise SystemExit('[mrs2] 找不到 MRS2 安装目录：请用 --mrs2 <安装根> 指定，或设置环境变量 MRS2_HOME。\n'
                     '       判定标志: <安装根>\\resources\\app\\resources\\win32\\components\\WCH\\manifest.json')


# ---------------------------------------------------------------- toolchain

def load_toolchains(inst):
    """解析 Toolchain\\sub_manifest.json → [{name, dir, prefix, gcc, g++, gdb, type, version}]"""
    mf = os.path.join(inst.toolchain_dir, 'sub_manifest.json')
    if not os.path.isfile(mf):
        return []
    out = []
    try:
        data = json.loads(read_text(mf))
    except Exception as e:
        raise SystemExit('[mrs2] 工具链清单解析失败 %s: %s' % (mf, e))
    for d in data.get('details', []):
        if d.get('status') != 2:  # 未安装
            continue
        tdir = os.path.normpath(os.path.join(inst.toolchain_dir, d.get('path', '.')))
        prefix = d.get('other_tool_prefix', '')
        cc = d.get('compiler_c_executable', {}).get('name') or (prefix + 'gcc')
        cpp = d.get('compiler_cpp_executable', {}).get('name') or (prefix + 'g++')
        out.append({
            'name': d.get('name', ''), 'type': d.get('type', ''), 'version': d.get('version', ''),
            'dir': tdir, 'prefix': prefix, 'gcc': prefix + 'gcc' if not cc else cc,
            'gpp': cpp, 'gdb': d.get('debugger_executable', {}).get('name') or (prefix + 'gdb'),
            'objcopy': prefix + 'objcopy', 'objdump': prefix + 'objdump',
            'ar': prefix + 'ar', 'size': prefix + 'size', 'label': d.get('label', ''),
        })
    return out


def select_toolchain(inst, request, proj_prefix=None):
    tcs = load_toolchains(inst)
    if not tcs:
        raise SystemExit('[mrs2] MRS2 未安装任何工具链: %s' % inst.toolchain_dir)
    if request and request.lower() not in ('auto', ''):
        for t in tcs:
            if t['name'].lower() == request.lower():
                return t
        raise SystemExit('[mrs2] 未找到工具链 "%s"；可用: %s' % (request, ', '.join(t['name'] for t in tcs)))
    # auto：按 .cproject 的 prefix 推断（riscv-none-embed- → GCC8，riscv-wch-elf- → GCC12）
    if proj_prefix:
        # 大小写折叠比较（token 与 manifest 拼写可能不一致）；同 prefix 多版本选编号大的
        cands = [t for t in tcs if t['prefix'].lower() == proj_prefix.lower()]
        if cands:
            def ver_key(t):
                m = re.search(r'(\d+)', t['name'])
                return int(m.group(1)) if m else 0
            return sorted(cands, key=ver_key)[-1]
    riscv = [t for t in tcs if t['type'] == 'RISC-V'] or tcs
    return riscv[0]


# ---------------------------------------------------------------- XML 工程

try:
    import xml.etree.ElementTree as ET
except ImportError:  # pragma: no cover
    raise SystemExit('[mrs2] 需要 Python 标准库 xml.etree')


def _tail(s):
    return s.rsplit('.', 1)[-1] if s else ''


class Option:
    def __init__(self, el):
        self.el = el
        self.super = el.get('superClass', '')
        self.vtype = el.get('valueType', '')

    def match(self, suffix):
        return self.super.endswith('.' + suffix) if '.' in suffix else self.super.endswith('.' + suffix)


class Project:
    def __init__(self, root):
        self.root = os.path.normpath(os.path.abspath(root))
        if not os.path.isdir(self.root):
            raise SystemExit('[mrs2] 工程目录不存在: %s' % self.root)
        self.marker = None          # 'wvproj' | 'project'
        self.wvproj = None
        for fn in sorted(os.listdir(self.root)):
            if fn.lower().endswith('.wvproj'):
                self.marker, self.wvproj = 'wvproj', fn
                break
        pfile = os.path.join(self.root, '.project')
        if not self.marker and os.path.isfile(pfile):
            self.marker = 'project'
        if not self.marker:
            raise SystemExit('[mrs2] 不是 MRS2 工程（无 *.wvproj / .project 标记）: %s' % self.root)
        self.name = os.path.basename(self.root)
        self.natures = []
        self.linked = {}            # 显示名 → locationURI 原文
        self.is_cpp = False
        if os.path.isfile(pfile):
            self._load_project_file(pfile)
        self.cproject_path = os.path.join(self.root, '.cproject')
        self.opts = []
        self.config_name = 'obj'
        self.artifact_name = '${ProjName}'
        self.artifact_ext = 'elf'
        self.artifact_type = 'exe'
        self.source_entries = []    # [(name|'root', [tokens])]
        if os.path.isfile(self.cproject_path):
            self._load_cproject()
        self.template_path = os.path.join(self.root, '.template')
        self.template = self._load_template() if os.path.isfile(self.template_path) else {}

    # ---- .project
    def _load_project_file(self, pfile):
        try:
            tree = ET.parse(pfile)
        except ET.ParseError as e:
            raise SystemExit('[mrs2] .project 解析失败（XML 已损坏？）%s: %s' % (pfile, e))
        r = tree.getroot()
        n = r.findtext('name')
        if n:
            self.name = n.strip()
        for nat in r.iter('nature'):
            self.natures.append((nat.text or '').strip())
        self.is_cpp = 'org.eclipse.cdt.core.cxxnature' in self.natures
        for link in r.iter('link'):
            nm = (link.findtext('name') or '').strip()
            loc = link.findtext('locationURI') or link.findtext('location') or ''
            if nm:
                self.linked[nm] = loc.strip()

    # ---- .cproject
    def _load_cproject(self):
        try:
            tree = ET.parse(self.cproject_path)
        except ET.ParseError as e:
            raise SystemExit('[mrs2] .cproject 解析失败（XML 已损坏？先备份再检查）%s: %s' % (self.cproject_path, e))
        r = tree.getroot()
        config = None
        for cfg in r.iter('configuration'):
            if cfg.get('name'):
                config = cfg
                break
        if config is None:
            raise SystemExit('[mrs2] .cproject 中找不到 configuration: %s' % self.cproject_path)
        self.config_name = config.get('name', 'obj')
        self.artifact_name = config.get('artifactName', '${ProjName}')
        bat = config.get('buildArtefactType', '')
        self.artifact_type = 'staticLibrary' if bat.endswith('staticLibrary') else 'exe'
        for opt in config.iter('option'):
            self.opts.append(Option(opt))
        for se in config.iter('entry'):
            if se.get('kind') != 'sourcePath':
                continue
            nm = (se.get('name') or '').strip()
            excl = [t for t in (se.get('excluding') or '').split('|') if t]
            self.source_entries.append((nm or 'root', excl))
        self.artifact_ext = ('a' if self.artifact_type == 'staticLibrary'
                             else (self.option_string('buildartifact.extension') or 'elf'))

    # ---- option 访问
    def _find(self, suffix):
        for o in self.opts:
            if o.super.endswith(suffix):
                return o.el
        return None

    def option_bool(self, suffix, default=False):
        el = self._find(suffix)
        if el is None:
            return default
        return el.get('value', '').lower() == 'true'

    def option_string(self, suffix):
        el = self._find(suffix)
        return el.get('value') if el is not None else None

    def option_enum(self, suffix):
        v = self.option_string(suffix)
        return v.rsplit('.', 1)[-1] if v else None

    def option_list(self, suffix):
        el = self._find(suffix)
        if el is None:
            return []
        out = []
        for v in el.findall('listOptionValue'):
            val = v.get('value', '')
            if val:
                out.append(val)
        return out

    def prefix(self):
        return self.option_string('option.command.prefix') or ''

    # ---- .template
    def _load_template(self):
        props = {}
        for line in read_text(self.template_path).splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('!'):
                continue
            if '=' in line:
                k, _, v = line.partition('=')
                props[k.strip()] = v.strip()
        return props

    # ---- 路径/宏解析
    def _resolve_link_target(self, loc):
        """解析链接文件夹的 locationURI（PARENT-N / 绝对 / 相对）。"""
        v = (loc or '').strip().strip('"').replace('${ProjName}', self.name)
        m = re.match(r'^PARENT-(\d+)-PROJECT_LOC(?:[/\\](.*))?$', v)
        if m:
            base = self.root
            for _ in range(int(m.group(1))):
                base = os.path.dirname(base)
            return os.path.normpath(os.path.join(base, (m.group(2) or '').replace('/', os.sep)))
        if re.match(r'^[A-Za-z]:[\\/]', v) or v.startswith('\\\\'):
            return os.path.normpath(v)
        return os.path.normpath(os.path.join(self.root, v.replace('/', os.sep)))

    def resolve_value(self, raw):
        """剥引号 + 宏解析 → 绝对路径；不可解析返回 None。

        处理两种 MRS2 现实形式：
        - ${workspace_loc:/${ProjName}/X} —— 替换后首段=工程名，须剥掉（否则多拼一层）
        - ${workspace_loc:/LED/StdPeriphDriver/inc} —— 首段=链接文件夹名时穿透到链接目标
        """
        v = raw.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        v = v.replace('${ProjName}', self.name)
        m = re.fullmatch(r'\$\{workspace_loc:/([^}]+)\}', v)
        if m:
            v = m.group(1)
        m = re.match(r'^PARENT-(\d+)-PROJECT_LOC(?:[/\\](.*))?$', v)
        if m:
            base = self.root
            for _ in range(int(m.group(1))):
                base = os.path.dirname(base)
            return os.path.normpath(os.path.join(base, (m.group(2) or '').replace('/', os.sep)))
        if re.match(r'^[A-Za-z]:[\\/]', v) or v.startswith('\\\\'):
            return os.path.normpath(v)
        if '${' in v:
            return None  # 未解析宏（如 workspace_loc 指向其他工程）
        segs = [s for s in v.replace('\\', '/').split('/') if s not in ('', '.')]
        # 首段=工程名：workspace_loc:/<ProjName>/rest → 工程根/rest
        if len(segs) > 1 and segs[0].lower() == self.name.lower():
            segs = segs[1:]
        # 首段=链接文件夹名：穿透到链接目标
        if segs:
            for ln, loc in self.linked.items():
                if ln.lower() == segs[0].lower():
                    target = self._resolve_link_target(loc)
                    return os.path.normpath(os.path.join(target, *segs[1:])) if os.path.isdir(target) else None
        return os.path.normpath(os.path.join(self.root, *segs) if segs else self.root)

    def build_dir(self):
        return os.path.join(self.root, self.config_name)

    def artifact_base(self):
        base = self.artifact_name.replace('${ProjName}', self.name).strip('"')
        return base if base else self.name


# ---------------------------------------------------------------- 扫描

def _strip_paired_quotes(v):
    """只剥成对包裹的首尾引号（保留值内部的字面引号，如 -DNAME="abc"）。"""
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


def _excluded(rel, tokens):
    """token 语义：含 / 的按前缀，裸 token 匹配直接子项（CDT 语义）。

    win32 上 token 与磁盘拼写可能大小写不一致（MRVC 实测 CH58x_led.c 案例），
    一律折叠比较。
    """
    rel = rel.replace('\\', '/').casefold()
    for tok in tokens:
        tok = tok.replace('\\', '/').casefold()
        if rel == tok or rel.startswith(tok + '/'):
            return True
    return False


def _walk_collect(base, tokens, skip_names, out, prefix=''):
    try:
        entries = sorted(os.listdir(os.path.join(base, prefix) if prefix else base))
    except OSError:
        return
    for name in entries:
        rel = (prefix + '/' + name) if prefix else name
        full = os.path.join(base, rel.replace('/', os.sep))
        if name.startswith(HIDDEN_PREFIX):
            continue
        if rel.casefold() in skip_names or _excluded(rel, tokens):
            continue
        if os.path.isdir(full):
            _walk_collect(base, tokens, skip_names, out, rel)
        else:
            ext = os.path.splitext(name)[1]
            if ext in SRC_C | SRC_CPP | SRC_ASM:
                out.append(rel)


def scan_sources(proj):
    """sourceEntries 语义扫描 → [相对路径]。

    命名 entry 可能是链接文件夹（工程内虚拟目录）：物理目录存在用物理目录，
    否则解析链接目标。相对路径统一以工程根/链接名前缀表示。
    """
    named = {}       # 目录名 → (该 entry 的 excluding tokens, 实际扫描目录)
    root_tokens = []
    for nm, excl in proj.source_entries:
        if nm == 'root':
            root_tokens.extend(excl)
        else:
            phys = os.path.join(proj.root, nm)
            if not os.path.isdir(phys):
                loc = proj.linked.get(nm)
                target = proj._resolve_link_target(loc) if loc else None
                phys = target if (target and os.path.isdir(target)) else None
            if phys:
                cur = named.get(nm)
                named[nm] = (cur[0] + excl if cur else list(excl), phys)
    skip = {n for n, _ in proj.source_entries if n != 'root'} | {'obj', proj.config_name}
    skip_fold = {s.casefold() for s in skip}
    sources = []
    _walk_collect(proj.root, root_tokens, skip_fold, sources)     # 根 entry（含裸排除）
    for d, (toks, phys) in named.items():
        # 命名 entry: excluding 相对该目录；物理目录在工程外时相对路径 = 链接名/...
        base_rel = None
        try:
            base_rel = os.path.relpath(phys, proj.root)
            if base_rel.startswith('..'):
                base_rel = d
            else:
                base_rel = base_rel.replace('\\', '/')
        except ValueError:
            base_rel = d
        sub = []
        _walk_collect(phys, toks, set(), sub)
        prefix = '' if base_rel == '.' else base_rel + '/'
        sources.extend(prefix + s for s in sub)
    return sorted(set(sources))


def infer_flash_address(sources):
    """按源文件名前缀推断下载地址（MRS2 flash.json 规则）。"""
    for rel in sources:
        base = os.path.basename(rel).lower()
        m = re.match(r'^startup_(ch[0-9a-z]+?)[_.]', base) or re.match(r'^(ch[0-9]+[a-z0-9]*?)_', base)
        if not m:
            continue
        chip = m.group(1)
        if chip.startswith('ch564'):
            return '0x08000000'
        if re.match(r'^ch5[6-9]', chip):
            return '0x00000000'
        if re.match(r'^ch(3|6)', chip):
            return '0x08000000'
    return None


# ---------------------------------------------------------------- flags

def is_wch_gcc(name):
    return name in ('GCC8', 'GCC12', 'GCC15')


def march_mabi(proj, tc_name):
    arch = proj.option_enum('target.isa.base') or 'rv32i'
    abi = proj.option_enum('target.abi.integer') or 'ilp32'
    # MRS2 生成器拆双键：-march 跟随 isa.fp，-mabi 跟随 abi.fp（两键可不同步）
    isa_fp = proj.option_enum('target.isa.fp') or 'none'
    abi_fp = proj.option_enum('target.abi.fp') or 'none'
    isa_fp_s = 'f' if isa_fp.endswith('single') else ('fd' if isa_fp.endswith('double') else '')
    abi_fp_s = 'f' if abi_fp.endswith('single') else ('fd' if abi_fp.endswith('double') else '')
    t = arch
    if arch not in ('rv32g', 'rv64g'):
        if proj.option_bool('target.isa.multiply'):
            t += 'm'
        if proj.option_bool('target.isa.atomic'):
            t += 'a'
        t += isa_fp_s
        if proj.option_bool('target.isa.compressed'):
            t += 'c'
        if is_wch_gcc(tc_name):
            if tc_name in ('GCC12', 'GCC15'):
                if proj.option_bool('target.isa.b'):
                    t += '_zba_zbb_zbc_zbs'
                if proj.option_bool('target.isa.zmmul'):
                    t += '_zmmul'
                if proj.option_bool('target.isa.xw'):
                    t += '_xw'
            elif proj.option_bool('target.isa.xw'):
                t += 'xw'
    mabi = abi + abi_fp_s
    return '-march=' + t, '-mabi=' + mabi


def common_flags(proj, tc_name, for_arm=False):
    if for_arm:
        return []  # ARM 目标选项命名空间不同（gnu arm 插件），此处不生成 target 旗标
    f = list(march_mabi(proj, tc_name))
    tune = proj.option_string('target.tune')
    if tune:
        tune = tune.rsplit('.', 1)[-1].strip()
        if tune and tune.lower() != 'default' and not re.search(r'\s', tune):
            f.append('-mtune=' + tune)
    cm = proj.option_enum('target.codemodel')
    if cm and cm != 'default' and cm != 'any':
        f.append('-mcmodel=med' + cm)
    f.append('-msmall-data-limit=' + (proj.option_string('target.smalldatalimit') or '8'))
    al = proj.option_string('target.align')
    if al:
        al = al.rsplit('.', 1)[-1].lower()
        if al == 'strict':
            f.append('-mstrict-align')
        elif al == 'nostrict':
            f.append('-mno-strict-align')
    f.append('-msave-restore' if proj.option_bool('target.saverestore') else '-mno-save-restore')
    f.append('-fmax-errors=20')  # MRS2 2.x 固定追加
    other = proj.option_string('target.other')
    if other:
        f += other.split()
    # optimization
    lvl = {'none': '-O0', 'optimize': '-O1', 'more': '-O2', 'most': '-O3',
           'fast': '-Ofast', 'debug': '-Og', 'z': '-Oz'}.get(proj.option_enum('optimization.level'), '-Os')
    f.append(lvl)
    for suf, flag in [
        ('optimization.messagelength', '-fmessage-length=0'),
        ('optimization.signedchar', '-fsigned-char'),
        ('optimization.functionsections', '-ffunction-sections'),
        ('optimization.datasections', '-fdata-sections'),
        ('optimization.nocommon', '-fno-common'),
        ('optimization.noinlinefunctions', '-fno-inline-functions'),
        ('optimization.freestanding', '-ffreestanding'),
        ('optimization.nobuiltin', '-fno-builtin'),
        ('optimization.spconstant', '-fsingle-precision-constant'),
        ('optimization.PIC', '-fPIC'),
        ('optimization.lto', '-flto'),
        ('optimization.nomoveloopinvariants', '-fno-move-loop-invariants'),
    ]:
        if proj.option_bool(suf):
            f.append(flag)
    if is_wch_gcc(tc_name):
        if proj.option_bool('optimization.mrs.highcode'):
            f.append('--param=highcode-gen-section-name=1')
        if proj.option_bool('optimization.mrs.asmsoftlib'):
            f += ['-Xassembler', '-wchsoftlib']
        if proj.option_bool('optimization.mrs.pipe'):
            f.append('-pipe')
        if proj.option_bool('optimization.mrs.caret'):
            f.append('-fno-diagnostics-show-caret')
    o = proj.option_string('optimization.other')
    if o:
        f += o.split()
    # warnings
    for suf, flag in [
        ('warnings.syntaxonly', '-fsyntax-only'), ('warnings.pedantic', '-pedantic'),
        ('warnings.pedanticerrors', '-pedantic-errors'), ('warnings.nowarn', '-w'),
        ('warnings.toerrors', '-Werror'), ('warnings.unused', '-Wunused'),
        ('warnings.uninitialized', '-Wuninitialized'), ('warnings.allwarn', '-Wall'),
        ('warnings.extrawarn', '-Wextra'), ('warnings.missingdeclaration', '-Wmissing-declarations'),
        ('warnings.conversion', '-Wconversion'), ('warnings.pointerarith', '-Wpointer-arith'),
        ('warnings.padded', '-Wpadded'), ('warnings.shadow', '-Wshadow'),
        ('warnings.logicalop', '-Wlogical-op'), ('warnings.agreggatereturn', '-Waggregate-return'),
        ('warnings.floatequal', '-Wfloat-equal'),
    ]:
        if proj.option_bool(suf):
            f.append(flag)
    o = proj.option_string('warnings.other')
    if o:
        f += o.split()
    # debug
    dl = proj.option_enum('debugging.level') or 'default'
    skip_fmt = False
    if dl == 'none':
        skip_fmt = True
    elif dl == 'minimal':
        f.append('-g1')
    elif dl == 'max':
        f.append('-g3')
    else:
        f.append('-g')
    if not skip_fmt:
        fmt = {'gdb': '-ggdb', 'stabs': '-gstabs', 'stabsplus': '-gstab+',
               'dwarf2': '-gdwarf-2', 'dwarf3': '-gdwarf-3', 'dwarf4': '-gdwarf-4',
               'dwarf5': '-gdwarf-5'}.get(proj.option_enum('debugging.format'))
        if fmt:
            f.append(fmt)
    o = proj.option_string('debugging.other')
    if o:
        f += o.split()
    if proj.option_bool('debugging.prof'):
        f.append('-p')
    if proj.option_bool('debugging.gprof'):
        f.append('-pg')
    return f


def lang_std(proj):
    std = proj.option_enum('c.compiler.std')
    return ['-std=' + std] if std else []


def include_flags(proj, suffix, warn_missing=True):
    out, missing = [], []
    for raw in proj.option_list(suffix):
        p = proj.resolve_value(raw)
        if p is None:
            missing.append(raw + ' (宏不可解析，已丢弃)')
            continue
        if not os.path.isdir(p):
            missing.append(p + ' (不存在，MRS 同样会丢弃)')
            continue
        out += ['-I', p]
    return out, missing


def define_flags(proj, suffix):
    out = []
    for raw in proj.option_list(suffix):
        out.append('-D' + _strip_paired_quotes(raw))
    return out


def linker_flags(proj, tc_name, side=None):
    side = side or ('cpp' if proj.is_cpp else 'c')
    f = []
    for raw in proj.option_list(side + '.linker.scriptfile'):
        p = proj.resolve_value(raw)
        if p:
            f += ['-T', p]
    if proj.option_bool(side + '.linker.nostart'):
        f.append('-nostartfiles')
    if proj.option_bool(side + '.linker.nodeflibs'):
        f.append('-nodefaultlibs')
    if proj.option_bool(side + '.linker.nostdlibs'):
        f.append('-nostdlib')
    if proj.option_bool(side + '.linker.gcsections'):
        f += ['-Xlinker', '--gc-sections']
    if proj.option_bool(side + '.linker.strip'):
        f.append('-s')
    for raw in proj.option_list(side + '.linker.paths'):
        p = proj.resolve_value(raw)
        if p:
            f += ['-L', p]
    for raw in proj.option_list(side + '.linker.flags'):
        if raw:
            f += ['-Xlinker', _strip_paired_quotes(raw)]
    f.append('-Wl,-Map=%s' % os.path.join(proj.build_dir(), proj.artifact_base() + '.map'))
    if proj.option_bool(side + '.linker.cref'):
        f += ['-Xlinker', '--cref']
    if proj.option_bool(side + '.linker.usenewlibnano'):
        f.append('--specs=nano.specs')
    if proj.option_bool(side + '.linker.useprintffloat'):
        f.append('-u _printf_float')
    if proj.option_bool(side + '.linker.usescanffloat'):
        f.append('-u _scanf_float')
    if proj.option_bool(side + '.linker.usenewlibnosys'):
        f.append('--specs=nosys.specs')
    o = proj.option_string(side + '.linker.other')
    if o:
        f += o.split()
    # WCH 专属库
    if is_wch_gcc(tc_name):
        if proj.option_bool(side + '.linker.iqmath'):
            f.append('-lIQmath_RV32')
        picolibc = proj.option_enum(side + '.linker.picolibc') or 'disabled'
        if picolibc == 'disabled':
            if proj.option_bool(side + '.linker.printf'):
                f.append('-lprintf')
            if proj.option_bool(side + '.linker.printfloat'):
                f.append('-lprintfloat')
    libs = [_strip_paired_quotes(v) for v in proj.option_list(side + '.linker.libs')]
    return f, (libs or ['m'])


# ---------------------------------------------------------------- 芯片库

def scan_chipdb(inst):
    db = {'available': os.path.isdir(inst.sdk_dir), 'series': []}
    if not db['available']:
        return db
    for arch in sorted(os.listdir(inst.sdk_dir)):
        archp = os.path.join(inst.sdk_dir, arch)
        if not os.path.isdir(archp):
            continue
        for series in sorted(os.listdir(archp)):
            sp = os.path.join(archp, series)
            if not os.path.isdir(sp):
                continue
            info = {'arch': arch, 'series': series, 'mcu_type': series, 'address': '', 'chip_id': None,
                    'caps': {}, 'models': [], 'toolchain_default': '', 'abis': {}}
            for rtos in sorted(os.listdir(sp)):
                rp = os.path.join(sp, rtos)
                if not os.path.isdir(rp):
                    continue
                fj = os.path.join(rp, '%s-flash.json' % series)
                if os.path.isfile(fj):
                    try:
                        d = json.loads(read_text(fj))
                        info['mcu_type'] = d.get('type', series)
                        info['address'] = d.get('flash_address', '')
                        info['chip_id'] = d.get('id')
                        info['caps'] = {k: v for k, v in d.items() if k.startswith('support_')}
                    except Exception:
                        pass
                tj = os.path.join(rp, '%s-targetProcessor.json' % series)
                if os.path.isfile(tj) and not info['abis']:
                    try:
                        d = json.loads(read_text(tj))
                        info['abis'] = {k: d.get(k) for k in ('architecture', 'integer_ABI', 'floating_point',
                                                              'compressed_extension', 'multiply_extension',
                                                              'atomic_extension', 'extra_compressed_extension')}
                        info['toolchain_default'] = (d.get('component_toolchain') or '').split(':')[-1]
                    except Exception:
                        pass
                if rtos == 'NoneOS':
                    for z in sorted(os.listdir(rp)):
                        if z.lower().endswith('.zip'):
                            info['models'].append(os.path.splitext(z)[0])
            db['series'].append(info)
    return db


# ---------------------------------------------------------------- 子命令

def cmd_find(args):
    root = os.path.abspath(args.dir)
    depth = args.depth
    projects, solutions = [], []
    for cur, dirs, files in os.walk(root):
        rel = os.path.relpath(cur, root)
        lvl = 0 if rel == '.' else rel.count(os.sep) + 1
        dirs[:] = [d for d in sorted(dirs) if not d.startswith(HIDDEN_PREFIX)]
        if lvl >= depth:
            dirs[:] = []
        wv = [f for f in files if f.lower().endswith('.wvproj')]
        if wv:
            projects.append({'dir': cur, 'marker': 'wvproj', 'wvproj': wv[0], 'name': wv[0][:-len('.wvproj')]})
            dirs[:] = []
            continue
        if '.project' in files:
            projects.append({'dir': cur, 'marker': 'project', 'wvproj': None, 'name': os.path.basename(cur)})
            dirs[:] = []
            continue
        for f in files:
            if f.lower().endswith('.wvsln'):
                solutions.append({'file': os.path.join(cur, f), 'name': f[:-len('.wvsln')]})
    out = {'root': root, 'projects': projects, 'solutions': solutions, 'count': len(projects)}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    for s in solutions:
        print('[solution] %s' % s['file'])
    for p in projects:
        print('[%-7s] %s   (%s)' % (p['marker'], p['dir'], p['name']))
    print('-- %d 个工程, %d 个 solution (深度 %d)' % (len(projects), len(solutions), depth))


# ---- 路径字符实测矩阵（references/build.md「路径字符与 recipe 执行 shell」，逐字符实测定版）
# recipe 经 MRS2 make bundle 的 sh 执行（PATH 上有 sh.exe 时），判定 = make 规则词 + sh 展开
# 两层。此处只给警告，不做拒绝——工程仍可解析、可手工组装命令编译。
def path_char_warnings(root, linked, sources, user_objs, libs):
    ws = []
    if '`' in root:
        ws.append('工程路径含反引号 (%s): sh 在双引号内仍命令替换, MRS2/MRVC 均无法构建' % root)
    if any(lf.get('resolved') for lf in linked) and (';' in root or '#' in root):
        ws.append('工程路径含 ; 或 # 且带链接目录: 链接规则 prereq 为绝对路径, 字符进 make 规则词'
                  '不可表达 (MRS2 同败, 其还会把 # 误写成 %)')
    for lf in linked:
        rp = lf.get('resolved')
        bad = [c for c in ';#`' if rp and c in rp]
        if bad:
            ws.append('链接目录 %s 解析路径含 %s: 不可构建 (%s)' % (lf['name'], '/'.join(bad), rp))
    bad_objs = [o for o in user_objs if re.search(r"[;#`&()'\[\]]", o)]
    if bad_objs:
        ws.append('Other Objects 含 ; # 反引号 & ( ) \' [ ]: 链接配方无引号展开, 会拆命令/破引号/'
                  'glob 到错误对象: %s' % ' | '.join(bad_objs[:3]))
    bad_libs = [l for l in libs if not re.fullmatch(r'[A-Za-z0-9._+-]+', l)]
    if bad_libs:
        ws.append('库名仅允许字母/数字/._+- (其余字符会在链接 sh 中执行命令): %s' % ', '.join(bad_libs))
    bad_srcs = [s for s in sources if re.search(r"[();#`]", os.path.basename(s))]
    if bad_srcs:
        ws.append('源文件名含 ( ) ; # 反引号不在支持范围: %s' % ', '.join(bad_srcs[:3]))
    return ws


def project_summary(proj, inst=None):
    tc_prefix = proj.prefix()
    tc = None
    tc_name = ''
    if inst:
        try:
            tc = select_toolchain(inst, 'auto', tc_prefix)
            tc_name = tc['name']
        except SystemExit:
            pass
    for_arm = bool(tc and tc['type'] == 'ARM')
    common = common_flags(proj, tc_name or 'GCC12', for_arm=for_arm)
    inc, inc_missing = include_flags(proj, 'c.compiler.include.paths')
    asm_inc, _ = include_flags(proj, 'assembler.include.paths', warn_missing=False)
    defs = define_flags(proj, 'c.compiler.defs')
    lflags, libs = linker_flags(proj, tc_name or 'GCC12')
    sources = scan_sources(proj)
    linked = []
    for nm, loc in proj.linked.items():
        rp = None
        m = re.match(r'^PARENT-(\d+)-PROJECT_LOC(?:[/\\](.*))?$', loc.replace('${ProjName}', proj.name))
        if m:
            base = proj.root
            for _ in range(int(m.group(1))):
                base = os.path.dirname(base)
            rp = os.path.normpath(os.path.join(base, m.group(2) or ''))
        elif re.match(r'^[A-Za-z]:[\\/]', loc):
            rp = os.path.normpath(loc)
        linked.append({'name': nm, 'raw': loc, 'resolved': rp,
                       'exists': bool(rp and os.path.exists(rp))})
    user_objs = [_strip_paired_quotes(v)
                 for v in proj.option_list(('cpp' if proj.is_cpp else 'c') + '.linker.otherobjs')]
    warnings = path_char_warnings(proj.root, linked, sources, user_objs, libs)
    tmpl = proj.template
    address = tmpl.get('Address') or infer_flash_address(sources) or ''
    chip = None
    if inst:
        series = tmpl.get('Series')
        if series:
            for s in scan_chipdb(inst)['series']:
                if s['series'].lower() == series.lower():
                    chip = {'series': s['series'], 'mcu_type': s['mcu_type'], 'flash_address': s['address'],
                            'chip_id': s['chip_id'], 'caps': s['caps']}
                    break
    art_base = proj.artifact_base()
    bdir = proj.build_dir()
    artifacts = {ext: os.path.join(bdir, '%s.%s' % (art_base, ext)) for ext in ('elf', 'hex', 'bin', 'a')}
    return {
        'dir': proj.root, 'name': proj.name, 'marker': proj.marker, 'is_cpp': proj.is_cpp,
        'config_name': proj.config_name, 'build_dir': bdir,
        'artifact_type': proj.artifact_type, 'artifact_base': art_base, 'artifact_ext': proj.artifact_ext,
        'toolchain_prefix': tc_prefix, 'toolchain_selected': tc_name,
        'march_mabi': common[:2] if not for_arm else [],
        'common_flags': common, 'std': lang_std(proj),
        'includes_resolved': [inc[i + 1] for i in range(0, len(inc), 2)],
        'includes_missing': inc_missing, 'asm_includes_resolved': [asm_inc[i + 1] for i in range(0, len(asm_inc), 2)],
        'defines': defs, 'linker_flags': lflags, 'libs': libs,
        'source_entries': [{'entry': n, 'excluding': e} for n, e in proj.source_entries],
        'sources': sources,
        'source_count': {k: sum(1 for s in sources if os.path.splitext(s)[1] in v)
                         for k, v in (('c', SRC_C), ('cpp', SRC_CPP), ('asm', SRC_ASM))},
        'linked_folders': linked, 'build_warnings': warnings,
        'template': tmpl, 'flash_address': address,
        'chipdb': chip,
        'artifacts': {k: (v if os.path.isfile(v) else None) for k, v in artifacts.items()},
        'natures': proj.natures,
    }


def cmd_show(args):
    proj = Project(args.dir)
    inst = None
    try:
        inst = find_install(args.mrs2)
    except SystemExit:
        pass
    s = project_summary(proj, inst)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return
    print('工程:    %s  (%s)' % (s['name'], s['dir']))
    print('标记:    %s   C++: %s   构建: %s/' % (s['marker'], s['is_cpp'], s['config_name']))
    for w in s['build_warnings']:
        print('警告:    %s' % w)
    print('产物:    %s.%s (%s)' % (s['artifact_base'], s['artifact_ext'], s['artifact_type']))
    print('工具链:  prefix=%s  选中=%s' % (s['toolchain_prefix'] or '(未设)', s['toolchain_selected'] or '(需安装)'))
    if s['march_mabi']:
        print('目标:    %s %s' % tuple(s['march_mabi']))
    print('公共旗标: %s' % ' '.join(s['common_flags']))
    if s['std']:
        print('语言:    %s' % ' '.join(s['std']))
    print('包含:    %s' % (', '.join(s['includes_resolved']) or '(无)'))
    for m in s['includes_missing']:
        print('         [丢] %s' % m)
    if s['defines']:
        print('宏定义:  %s' % ' '.join(s['defines']))
    print('链接:    %s | 库: %s' % (' '.join(s['linker_flags']), ' '.join('-l' + l for l in s['libs'])))
    for e in s['source_entries']:
        print('entry:   %-16s excluding=%d 项' % (e['entry'], len(e['excluding'])))
    print('源文件:  %s   (共 %d)' % (s['source_count'], len(s['sources'])))
    for lf in s['linked_folders']:
        ok = 'OK' if lf['exists'] else '缺失'
        print('链接:    %s -> %s [%s]' % (lf['name'], lf['resolved'] or lf['raw'], ok))
    t = s['template']
    if t:
        print('下载:    Mcu=%s Address=%s TargetPath=%s EraseAll=%s Verify=%s Reset=%s' % (
            t.get('Mcu Type', '?'), t.get('Address', '(缺省)'), t.get('Target Path', '?'),
            t.get('Erase All', '?'), t.get('Verify', '?'), t.get('Reset', '?')))
    if s['chipdb']:
        c = s['chipdb']
        print('芯片库:  %s / %s  chipID=%s  地址=%s' % (c['series'], c['mcu_type'], c['chip_id'], c['flash_address']))
    have = ['%s(%s)' % (k, time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(v)))) for k, v in s['artifacts'].items() if v]
    print('现有产物: %s' % (', '.join(have) or '无'))
    if args.sources:
        for x in s['sources']:
            print('  %s' % x)


def cmd_toolchain(args):
    inst = find_install(args.mrs2)
    tcs = load_toolchains(inst)
    if args.json:
        print(json.dumps({'install': inst.win32, 'toolchains': tcs}, ensure_ascii=False, indent=2))
        return
    print('MRS2: %s' % inst.win32)
    for t in tcs:
        ok = os.path.isfile(os.path.join(t['dir'], 'bin', t['gcc'] + '.exe'))
        print('  %-6s %-8s %-22s %s  [%s]' % (t['name'], t['type'], t['prefix'], t['dir'],
                                              '可用' if ok else '缺失'))
    print('make:  %s' % os.path.join(inst.make_bin, 'make.exe'))


def cmd_chips(args):
    inst = find_install(args.mrs2)
    db = scan_chipdb(inst)
    if args.series:
        db['series'] = [s for s in db['series'] if args.series.lower() in s['series'].lower()]
    if args.json:
        print(json.dumps(db, ensure_ascii=False, indent=2))
        return
    for s in db['series']:
        print('%-7s %-12s type=%-16s 地址=%-12s chipID=%-4s 型号=%d' % (
            s['arch'], s['series'], s['mcu_type'], s['address'] or '?', s['chip_id'], len(s['models'])))
        if args.models:
            print('   %s' % ', '.join(s['models']))


def cmd_sln(args):
    sln_path = os.path.abspath(args.file)
    sln_dir = os.path.dirname(sln_path)
    raw = read_text(sln_path)
    config_lines, build_order, members, dropped = [], None, [], []
    seen = set()
    for line in raw.splitlines():
        t = line.strip()
        if not t or t.lower().endswith('.wvsln:'):
            continue
        if t.startswith('-'):
            config_lines.append(t)
            continue
        if t.startswith('BuildOrder='):
            build_order = [x for x in t[len('BuildOrder='):].split(',') if x]
            continue
        p = t if os.path.isabs(t) else os.path.normpath(os.path.join(sln_dir, t))
        key = p.lower() if os.name == 'nt' else p
        if key in seen:
            continue
        seen.add(key)
        entry = {'raw': t, 'resolved': p, 'exists': os.path.isdir(p)}
        (members if entry['exists'] else dropped).append(entry)
    if build_order:
        def rank(m):
            nm = os.path.basename(m['resolved'])
            for wv in [f for f in os.listdir(m['resolved']) if f.lower().endswith('.wvproj')] if os.path.isdir(m['resolved']) else []:
                nm = wv[:-len('.wvproj')]
                break
            return build_order.index(nm) if nm in build_order else len(build_order)
        members.sort(key=rank)
    out = {'file': sln_path, 'config_lines': config_lines, 'build_order': build_order,
           'members': members, 'dropped': dropped}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    for c in config_lines:
        print('config: %s' % c)
    print('BuildOrder: %s' % (', '.join(build_order) if build_order else '(缺省=文件行序)'))
    for m in members:
        print('member: %s' % m['resolved'])
    for d in dropped:
        print('MISSING: %s (来自 %s)' % (d['resolved'], d['raw']))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog='mrs2.py', description='MRS2 工程命令行工具（无需 MRS2 IDE）')
    ap.add_argument('--mrs2', help='MRS2 安装根目录（默认探测 C:\\MounRiver\\MounRiver_Studio2 等）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('find', help='递归发现工程/solution')
    p.add_argument('dir')
    p.add_argument('--depth', type=int, default=6)
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser('show', help='解析工程配置摘要')
    p.add_argument('dir')
    p.add_argument('--json', action='store_true')
    p.add_argument('--sources', action='store_true', help='列出全部源文件')
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser('toolchain', help='列出工具链')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_toolchain)

    p = sub.add_parser('chips', help='扫描芯片库')
    p.add_argument('--series', help='系列名过滤（子串）')
    p.add_argument('--models', action='store_true', help='列出型号')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_chips)

    p = sub.add_parser('sln', help='解析 .wvsln')
    p.add_argument('file')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_sln)


    args = ap.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
