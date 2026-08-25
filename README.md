# NetCore Framework

网络运维一体化平台底层框架：基于插件机制，提供配置备份与比对、CMDB 资产管理、网络拓扑、运维工具箱、知识库等能力。

> 本仓库为**底层框架**，不含业务插件。业务插件（cmdb / netconfig_guardian / ops_toolbox）为独立仓库，下载后放入 `plugins/` 即被自动识别。详见下方「插件（独立仓库）」。

## 特性

- **插件化架构**：`plugins/<name>/plugin.py` 即插即用，启动自动发现、加载、挂载路由与菜单，单插件故障不影响主框架。
- **统一鉴权**：JWT + 可选 TOTP 双因素；AES-256-GCM 前端加密登录凭据；登录失败 IP 临时封禁。
- **审计与通知**：全量操作审计日志（可导出）；邮件 / 企业微信 / 钉钉 / 飞书多渠道通知。
- **安全策略**：IP 黑白名单、登录失败锁定、HTTPS（自签名或自定义证书 + 反向协议跳转）。
- **单文件分发**：PyInstaller onefile，Windows / Linux 双平台；GitHub Actions 自动构建并发布 Release。
- **前端**：Vue 3 + Element Plus 离线全局构建，SPA + 前端路由接管；插件前端经 `/plugin-assets/<name>/` 动态注入。

## 技术栈

- 后端：Python 3.13 + FastAPI + SQLite
- 前端：Vue 3 + Element Plus（离线全局构建，运行时编译）
- 打包：PyInstaller onefile（Windows / Linux）

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `core/` | 框架核心（路由、鉴权、审计、HTTPS、插件管理、配置加载） |
| `plugins/` | 插件基类 `base_plugin.py` 与内置 `wiki_docs` 知识库插件 |
| `frontend/` | 前端静态资源（JS / CSS / HTML） |
| `wiki/` | 内置知识库文档（由 `wiki_docs` 插件提供） |
| `main.py` | 开发模式入口 |
| `build.py` | 单文件可执行构建（Win / Linux），由 CI 调用 |
| `requirements.txt` | 运行时依赖（全部 `==` 精确锁定，含所有插件依赖） |
| `.github/workflows/build.yml` | GitHub Actions 双平台自动构建（Win / Linux） |
| `wiki2/` | **本文档集**（教程 / 程序逻辑 / 解决方法 / 插件制作 / API 文档） |

## 插件（独立仓库）

本仓库仅含框架核心与 `wiki` 知识库插件。业务插件为独立 GitHub 仓库，下载后放入框架 `plugins/` 目录即被自动识别：

| 插件目录 | 仓库 | 说明 |
| --- | --- | --- |
| `plugins/cmdb/` | NetCore-cmdb | 资产配置管理（CMDB） |
| `plugins/netconfig_guardian/` | NetCore-netconfig_guardian | 数通配置卫士（配置备份 / 比对 / 巡检） |
| `plugins/ops_toolbox/` | NetCore-ops_toolbox | 运维常用工具箱 |

部署：将对应仓库的 `<插件名>/` 目录整体复制到框架 `plugins/` 下，重启框架即自动加载。各插件仓库自带 `requirements.txt`，但主框架 `requirements.txt` 已含全部插件依赖，无需重复安装。

## 快速开始（开发模式）

```bash
pip install -r requirements.txt
python main.py
```

访问 http://localhost:8080 ，默认账号 `admin` / `Admin@123!`。

## 构建单文件可执行

本地手动构建：

```bash
python build.py --target win      # Windows
python build.py --target linux     # Linux
```

或通过 GitHub Actions 自动构建（无需本地脚本）：打 `v*` 标签推送，或手动触发 workflow，CI 会在 Windows / Linux runner 上分别产出 `netcore-framework.exe` 与 `netcore-framework`，并在打 tag 时自动发布到 Release。详见 [.github/workflows/build.yml](.github/workflows/build.yml)。

## 文档

- 运行期内置文档：登录后左侧「使用文档」菜单（来自 `wiki/` 目录）。
- 开发者文档集：**`wiki2/`** 目录，包含：
  - [教程](wiki2/教程.md)
  - [程序逻辑](wiki2/程序逻辑.md)
  - [解决方法](wiki2/解决方法.md)
  - [插件制作过程](wiki2/插件制作过程.md)
  - [API 文档](wiki2/API文档.md)

## 许可证

Apache-2.0，详见 [LICENSE](LICENSE)。
