#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetCore Framework 跨平台单文件构建脚本
================================================
将本项目打包为「单文件」可执行程序：
  - Windows  -> dist/netcore-framework.exe
  - Linux    -> dist/netcore-framework

用法（在项目根目录执行）：
  python build.py                  # 构建当前操作系统对应的可执行文件（默认）
  python build.py --target win     # 强制构建 Windows（需在 Windows / Docker-Windows 中运行）
  python build.py --target linux   # 强制构建 Linux（需在 Linux / Docker 中运行）
  python build.py --target all     # 构建两者（跨系统部分需要 Docker 支持）
  python build.py --dist outdir    # 指定最终产物输出目录（默认：项目根/dist）

设计要点：
  1. ROOT（项目根）取「本脚本所在目录」，不再写死绝对路径，因此可在
     Windows / Linux / macOS 上原样复用，也便于把整个项目拷贝到任意路径后构建。
  2. 本脚本在运行时动态生成 PyInstaller 的 .spec 文件（隐藏导入、排除项与
     原 build.spec 完全对齐），避免维护两份容易漂移的配置。
  3. PyInstaller 原生「不支持交叉编译」：在 Windows 上只能产出 EXE，
     在 Linux 上只能产出 Linux 可执行文件。要「一条命令生成两种」，请用
     --target all，并让本机具备 Docker：跨系统的那一个会借助 Dockerfile.linux
     在容器内构建，再把产物拷贝回宿主机的 --dist 目录。
  4. 运行环境需已安装 PyInstaller 及项目全部依赖（见 requirements.txt；
     数通配置卫士插件另需 netmiko），否则 collect_submodules 会跳过缺失包并告警。
"""
import argparse
import datetime
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys

# ---- 项目根目录：build.py 所在目录（跨平台、不依赖写死路径） -----------------
ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- 隐藏导入：与 build.spec 对齐 -------------------------------------------------
# 需要递归收集子模块的包（缺失会被跳过并告警）
COLLECT_PKGS = ["core", "plugins", "uvicorn", "apscheduler", "jinja2", "netmiko",
                "paramiko", "pyftpdlib", "dns", "tftpy"]
# 必须显式加入的单一模块
STATIC_HIDDEN = [
    "pyotp", "qrcode", "httpx", "yaml", "cryptography",
    # 修复：cryptography 子模块为运行时 import（__init__.py 不主动导入
    # x509/backends），Linux 打包漏收集导致 ops_toolbox ssl_check 组件加载失败；
    # 显式补齐（Win 因 hook 收集差异碰巧正常，补齐后两平台一致）
    "cryptography.x509", "cryptography.hazmat", "cryptography.hazmat.backends",
    "starlette", "fastapi", "multipart", "encodings",
    # SQLite 由插件在运行时通过 importlib 动态加载，静态分析抓不到，必须显式加入
    "sqlite3",
    # SNMP 结果导出 Excel 依赖 openpyxl，运行时局部 import，需显式加入
    "openpyxl",
    "cv2", "numpy", "PIL", "PIL.Image", "PIL.ImageDraw",
]
# 排除项：避免把数据科学栈（pandas/scipy/torch）等拖进包体导致体积暴涨。
# 注意：numpy 不再排除——opencv(cv2) 强依赖 numpy，排除会导致二维码识别在 EXE 中崩溃。
EXCLUDES = [
    "pytest", "PyInstaller", "tkinter", "unittest", "doctest",
    "pygments", "rich",
    "pandas", "scipy", "torch", "matplotlib",
]


def _read_system_version() -> str:
    """从 core/config_loader.py 读取 SYSTEM_VERSION（如 ），供 EXE 版本资源。"""
    try:
        import re
        p = os.path.join(ROOT, "core", "config_loader.py")
        txt = open(p, encoding="utf-8").read()
        m = re.search(r'SYSTEM_VERSION\s*=\s*"([^"]+)"', txt)
        return m.group(1).strip() if m else "0.0.0.0"
    except Exception:  # noqa: BLE001
        return "0.0.0.0"


def _parse_version_tuple(ver: str):
    """> (2026, 8, 11, 8)（Windows VERSIONINFO 需要 4 段数字）"""
    try:
        date_part = ver.split("-")[0].strip()
        y = int(date_part[:4])
        m = int(date_part[4:6])
        d = int(date_part[6:8])
        if "-" in ver and ver.split("-")[1].lower().startswith("v"):
            n = int(ver.split("-")[1][1:].strip() or 0)
        else:
            n = 0
        return (y, m, d, n)
    except Exception:  # noqa: BLE001
        return (0, 0, 0, 0)


def _write_version_file(ver: str) -> str:
    """生成 PyInstaller Windows 版本资源文件（VERSIONINFO），返回路径（仅 Windows 使用）。"""
    tup = _parse_version_tuple(ver)
    filevers = "(%d, %d, %d, %d)" % tup
    prodvers = "(%d, %d, %d, %d)" % tup
    filever_str = "%d.%d.%d.%d" % tup
    content = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=%s,
    prodvers=%s,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '080404b0',
          [StringStruct('CompanyName', 'NetCore Team'),
           StringStruct('FileDescription', 'NetCore Framework'),
           StringStruct('FileVersion', '%s'),
           StringStruct('InternalName', 'netcore-framework'),
           StringStruct('OriginalFilename', 'netcore-framework.exe'),
           StringStruct('ProductName', 'NetCore Framework'),
           StringStruct('ProductVersion', '%s')]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""" % (filevers, prodvers, filever_str, ver)
    vp = os.path.join(ROOT, "build_generated_version.txt")
    with open(vp, "w", encoding="utf-8") as f:
        f.write(content)
    return vp

# 运行时生成的 spec 模板（用 token 替换，避免 .format 的 {} 冲突）
SPEC_TEMPLATE = r'''# -*- mode: python ; coding: utf-8 -*-
# 本文件由 build.py 自动生成，请勿手动修改；调整请改 build.py。
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = __ROOT__

hiddenimports = [
__HIDDEN__
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "frontend"), "frontend"),
        (os.path.join(ROOT, "wiki"), "wiki"),
        (os.path.join(ROOT, "plugins"), "plugins"),
    ],
    hiddenimports=hiddenimports,
    excludes=[
__EXCLUDES__
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="netcore-framework",
__VERSIONLINE__
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
__UPXDIR__
    console=True,
)
'''


def is_windows_host():
    return os.name == "nt"


def build_hiddenimports():
    """返回隐藏导入列表；对 COLLECT_PKGS 中已安装的包递归收集子模块。"""
    imps = list(STATIC_HIDDEN)
    for pkg in COLLECT_PKGS:
        try:
            if importlib.util.find_spec(pkg) is not None:
                from PyInstaller.utils.hooks import collect_submodules
                imps += collect_submodules(pkg)
            else:
                print(f"  [警告] 包 '{pkg}' 未安装，已跳过其隐藏导入收集（构建产物可能缺该模块）")
        except Exception as e:  # 尽可能稳健，单包失败不拖垮整体
            print(f"  [警告] 收集 '{pkg}' 子模块失败：{e}")
    return imps


def _upx_dir_line():
    """若项目 tools/ 目录内自带 upx(.exe)，返回 spec 用的 upx_dir 行，否则回退 PATH。

    这样 upx=True 才能真正生效（PyInstaller 需能定位 upx 可执行文件）。
    """
    exe_name = "upx.exe" if is_windows_host() else "upx"
    upx_path = os.path.join(ROOT, "tools", exe_name)
    if os.path.exists(upx_path):
        return "    upx_dir=%s," % repr(os.path.join(ROOT, "tools"))
    print("  [提示] 未找到 tools/%s，UPX 压缩将依赖系统 PATH；若无 upx 则跳过压缩。" % exe_name)
    return ""


def write_spec(target_path, override_version=None):
    """生成 .spec 到 target_path 并返回路径。

    Windows 构建时注入 EXE 版本资源（version=...VERSIONINFO 文件），
    使 exe 文件属性的「详细信息-产品版本」显示真实版本号。
    新增 override_version 参数——显式指定 EXE 版本戳（如仅插件升版、
    框架冻结时，用 --version  把 EXE 标为 V4，而不动 SYSTEM_VERSION）。
    """
    hidden = ",\n".join(f'        "{m}"' for m in build_hiddenimports())
    excludes = ",\n".join(f'              "{e}"' for e in EXCLUDES)
    version_line = ""
    if is_windows_host():
        ver = override_version or _read_system_version()
        vf = _write_version_file(ver)
        version_line = "    version=%s," % repr(vf)
    content = (SPEC_TEMPLATE
               .replace("__ROOT__", repr(ROOT))
               .replace("__HIDDEN__", hidden)
               .replace("__UPXDIR__", _upx_dir_line())
               .replace("__VERSIONLINE__", version_line)
               .replace("__EXCLUDES__", excludes))
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
    return target_path


def final_artifact_name():
    """产物文件名：Windows 带 .exe，其余不带。"""
    return "netcore-framework.exe" if is_windows_host() else "netcore-framework"


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def docker_available():
    return shutil.which("docker") is not None


def build_native(target, dist_dir, override_version=None):
    """在当前宿主机原生构建（要求宿主机 OS 与 target 一致）。"""
    os.makedirs(dist_dir, exist_ok=True)
    workpath = os.path.join(dist_dir, "_pyi_work")
    out_spec = os.path.join(ROOT, "build_generated.spec")
    write_spec(out_spec, override_version)
    print(f"[信息] 已生成 spec：{out_spec}")
    cmd = [sys.executable, "-m", "PyInstaller", out_spec,
           "--noconfirm", "--distpath", dist_dir, "--workpath", workpath]
    print(f"[执行] {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc
    built = os.path.join(dist_dir, final_artifact_name())
    if not os.path.exists(built):
        print(f"[错误] 未找到构建产物：{built}")
        return 1
    _report(built)
    return 0


def build_via_docker(target, dist_dir):
    """借助 Dockerfile.linux 在容器内构建 Linux 产物，再拷回 dist_dir。"""
    if not docker_available():
        print("[错误] 本机未检测到 Docker，无法自动构建跨系统产物。")
        print("        请在 Linux 宿主机上运行 `python build.py --target linux`，")
        print("        或安装 Docker 后重试；也可参考 wiki/03-构建与交付.md 的 Docker 命令。")
        return 2
    dockerfile = os.path.join(ROOT, "Dockerfile.linux")
    if not os.path.exists(dockerfile):
        print(f"[错误] 找不到 {dockerfile}，无法进行 Docker 构建。")
        return 2
    image = "nc-framework-build"
    print(f"[执行] docker build -f Dockerfile.linux -t {image} .")
    rc = subprocess.call(["docker", "build", "-f", "Dockerfile.linux", "-t", image, "."], cwd=ROOT)
    if rc != 0:
        return rc
    os.makedirs(dist_dir, exist_ok=True)
    # 容器内 --dist /out 直接输出到挂载卷；Windows 用 %cd%，Linux/macOS 用 $PWD
    mount = dist_dir if not is_windows_host() else dist_dir
    print(f"[执行] docker run --rm -v {mount}:/out {image}")
    rc = subprocess.call(["docker", "run", "--rm", "-v", f"{mount}:/out", image])
    return rc


def _report(path):
    size = os.path.getsize(path)
    print("------------------------------------------------------------")
    print(f"[完成] 产物：{path}")
    print(f"       体积：{size} 字节（≈{size / 1024 / 1024:.1f} MB）")
    print(f"       MD5 ：{md5_of(path)}")
    print(f"       时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("------------------------------------------------------------")


def main():
    ap = argparse.ArgumentParser(description="NetCore Framework 跨平台单文件构建")
    ap.add_argument("--target", choices=["win", "linux", "all", "auto"], default="auto",
                    help="构建目标平台（默认 auto=当前系统）")
    ap.add_argument("--dist", default=os.path.join(ROOT, "dist"),
                    help="最终产物输出目录（默认 项目根/dist）")
    ap.add_argument("--version", default=None,
                    help="覆盖 EXE 版本资源字符串（默认读取 core/config_loader.py 的 SYSTEM_VERSION）；"
                         "仅影响 EXE 文件属性「详细信息」的版本戳，不改动框架运行时版本")
    args = ap.parse_args()

    target = args.target
    if target == "auto":
        target = "win" if is_windows_host() else "linux"
    print(f"[信息] 目标平台：{target} ｜ 宿主机：{'Windows' if is_windows_host() else '非Windows'}")
    print(f"[信息] 项目根 ROOT：{ROOT}")

    # 拆分：把 target 解析为本机原生构建项 + 需要 Docker 的跨系统项
    native_ok = True
    docker_needed = False
    if target in ("win", "linux"):
        if (target == "win" and is_windows_host()) or (target == "linux" and not is_windows_host()):
            native_ok = build_native(target, args.dist, args.version) == 0
        else:
            # 跨系统且单机：尝试 Docker
            docker_needed = True
    elif target == "all":
        # 先原生构建当前系统
        cur = "win" if is_windows_host() else "linux"
        native_ok = build_native(cur, args.dist, args.version) == 0
        # 再构建另一个（用 Docker）
        other = "linux" if cur == "win" else "win"
        docker_needed = True
        if other == "win":
            print("[提示] 在非 Windows 宿主上构建 Windows 可执行文件不被支持，"
                  "请到 Windows 机器执行 `python build.py --target win`。")
            docker_needed = False  # 跳过

    if docker_needed:
        print("[信息] 当前为跨系统目标，尝试通过 Docker 构建另一平台产物……")
        rc = build_via_docker(target, args.dist)
        if rc != 0:
            print(f"[警告] Docker 构建未成功（返回码 {rc}），请按上述提示手动处理。")
            return rc

    if not native_ok:
        print("[错误] 原生构建失败，请检查依赖与 PyInstaller 安装。")
        return 1
    print("[完成] 构建流程结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
