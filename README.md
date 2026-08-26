# NetCore Framework

网络运维一体化平台底层框架：基于插件机制，提供配置备份与比对、CMDB 资产管理、网络拓扑、运维工具箱、知识库等能力。

> 本仓库为**底层框架**，不含业务插件。业务插件（cmdb / netconfig_guardian / ops_toolbox）为独立仓库，下载后放入 `plugins/` 即被自动识别。

## 特性

- **插件化架构**：`plugins/<name>/plugin.py` 即插即用，启动自动发现、加载、挂载路由与菜单，单插件故障不影响主框架
- **统一时间口径**：入库一律 UTC，展示按 `user_config.yaml → timezone` 换算为 `YYYY-MM-DD HH:MM:SS`（审计导出同口径，字段名 timestamp）
- **安全策略**：IP 白名单（放行+免锁定）/ 黑名单（封禁期 404）、失败锁定自动拉黑、TOTP 双因素、AES-256-GCM 加密登录、登录失败 IP 临时封禁；回环白名单仅首次初始化写入
- **审计与通知**：全量操作审计日志（按天滚动、可导出可清理）；邮件 / 企业微信 / 钉钉 / 飞书多渠道通知（模板渲染 + 频率限制）
- **HTTPS**：自签名或自定义证书 + 反向协议跳转；站点图标 SVG 化
- **单文件分发**：PyInstaller onefile，Windows / Linux 双平台；GitHub Actions 自动构建并发布 Release
- **前端**：Vue 3 + Element Plus 离线全局构建，SPA 前端路由接管；插件前端经 `/plugin-assets/<name>/` 动态注入

## 技术栈

后端 Python 3.13 + FastAPI + SQLite ｜ 前端 Vue 3 + Element Plus（离线）｜ 打包 PyInstaller onefile

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `core/` | 框架核心（路由、鉴权、审计、通知、会话、HTTPS、插件管理、配置加载、时间基准） |
| `plugins/` | 插件基类 `base_plugin.py` 与内置知识库插件 `wiki_docs`；`wiki/plugin_template/` 为插件模板工程 |
| `frontend/` | 前端静态资源（JS / CSS / HTML / favicon.svg） |
| `wiki/` | 内置文档集（运行时「使用文档」菜单内容）：快速开始、使用说明、API手册、配置说明、插件开发指南、程序逻辑与架构、部署运维、构建与交付、FAQ |
| `main.py` | 开发模式入口 |
| `build.py` | 单文件可执行构建（Win / Linux），由 CI 调用 |
| `tests/` | pytest 测试（uv 环境运行） |
| `dist/` | 构建产物目录（每次构建清空，仅留最新可执行文件） |

## 业务插件（独立仓库）

| 插件目录 | 说明 |
| --- | --- |
| `plugins/cmdb/` | 资产配置管理（CMDB） |
| `plugins/netconfig_guardian/` | 数通配置卫士（配置备份 / 比对 / 巡检） |
| `plugins/ops_toolbox/` | 运维常用工具箱 |

部署：将对应仓库的 `<插件名>/` 目录整体复制到程序目录 `plugins/` 下（注意不要多套一层仓库文件夹），重启框架即自动加载。主框架 requirements.txt 已含全部官方插件依赖。

## 快速开始（开发模式）

```bash
# 推荐使用 uv 创建环境
uv venv --python 3.13 .venv
uv pip install -r requirements.txt -r requirements-dev.txt --python .venv

# 测试
.venv/Scripts/python -m pytest tests -q        # Windows
.venv/bin/python -m pytest tests -q            # Linux

# 运行
python main.py
```

访问 `http(s)://localhost:8080`，默认账号 `admin / Admin@123!`（首次登录后请修改）。

## 构建单文件可执行

```bash
python build.py --target win      # Windows
python build.py --target linux    # Linux
```

或推送代码触发 GitHub Actions 自动构建；打 `v*` 标签或手动 workflow_dispatch 可发布 Release。

## 版本号规则

`变动日期-V序号`（如 `20260826-V6`）。谁改动谁升版：改框架升 `core/config_loader.py → SYSTEM_VERSION`，改某插件只升该插件版本号。详见内置文档《08-构建与交付》。

## 文档

运行时登录后左侧「使用文档」菜单（来自 `wiki/`），包含：

- 快速开始 / 使用说明（用户向）
- API手册 / 配置文件说明（集成与运维）
- 插件开发指南 / 程序逻辑与架构 / 构建与交付 / 部署运维 / FAQ（开发与运维）

## 许可证

Apache-2.0，详见 [LICENSE](LICENSE)。
