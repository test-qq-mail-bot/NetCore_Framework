"""
tests/conftest.py - 测试公共夹具

隔离 BASE_DIR（monkeypatch config_loader 常量），避免测试污染真实配置/数据目录。
"""
import os
import sys
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """把框架的运行期目录重定向到临时目录，确保测试零副作用。"""
    cfg_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    plugins_dir = tmp_path / "plugins"
    for d in (cfg_dir, data_dir, plugins_dir):
        d.mkdir(parents=True, exist_ok=True)
    # 延迟导入，确保已插入 sys.path
    import core.config_loader as cl
    monkeypatch.setattr(cl, "CONFIG_DIR", cfg_dir, raising=False)
    monkeypatch.setattr(cl, "DATA_DIR", data_dir, raising=False)
    monkeypatch.setattr(cl, "PLUGINS_DIR", plugins_dir, raising=False)
    monkeypatch.setattr(cl, "_config_cache", {}, raising=False)
    return {"config": cfg_dir, "data": data_dir, "plugins": plugins_dir}
