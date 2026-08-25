# API 文档（框架内置）

所有接口统一前缀 `/api`。除登录、加密密钥、健康检查、文档外，均需携带 `Authorization: Bearer <token>`（由 `Depends(get_current_user)` 校验）。

## 认证（/api/auth）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录。请求体 `{username, password, totp?}`（均 AES-256-GCM 密文）。成功返回 `token` 与 `is_default_password` 等 |
| POST | `/api/auth/totp/setup` | 生成 TOTP 绑定信息（需登录） |
| POST | `/api/auth/totp/verify` | 校验 TOTP 验证码并绑定（需登录） |
| POST | `/api/auth/logout` | 注销当前会话（需登录） |
| POST | `/api/auth/heartbeat` | 心跳续期，返回剩余有效秒数（需登录） |

## 安全（/api/security）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/security/whitelist` | 获取 IP 白名单 |
| POST | `/api/security/whitelist` | 添加白名单 `{ip, note?, expires_at?}` |
| DELETE | `/api/security/whitelist` | 删除白名单 `{ip}` |
| GET | `/api/security/blacklist` | 获取 IP 黑名单 |
| POST | `/api/security/blacklist` | 添加黑名单 `{ip, minutes, note?, expires_at?}` |
| DELETE | `/api/security/blacklist` | 删除黑名单 `{ip}` |
| GET | `/api/security/failure-policy` | 获取登录失败策略 |
| PUT | `/api/security/failure-policy` | 更新失败策略 |

> 白名单为「受信任免锁定放行」语义，非防火墙；命中黑名单返回 404 以隐藏后台。

## 通知（/api/notify）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/notify/send` | 发送通知 `{channels, title, content, priority?, recipients?, template_id?, source?}` |
| GET | `/api/notify/channels` | 渠道状态列表 |
| POST | `/api/notify/test/{channel}` | 测试指定渠道 |
| GET | `/api/notify/config` | 获取通知配置（敏感字段脱敏） |
| PUT | `/api/notify/config` | 保存通知配置（即时生效） |

## 审计日志（/api/logs/audit）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/logs/audit` | 分页查询。参数 `page/size(≤10000)/ip/result/action/start_date/end_date/sort_by/sort_order/filter_col/filter_values` |
| GET | `/api/logs/audit/export` | 导出 CSV / JSONL。`fmt=csv\|json`、`limit≤20000`；超出响应头标 `X-Audit-Truncated: true` |
| DELETE | `/api/logs/audit/clean` | 清理全部审计日志 |

## 系统（/api/system）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/system/crypto-key` | 公开：返回前端加密密钥、软件名/版本、内置名/版本、TOTP 开关 |
| GET | `/api/system/health` | 公开：健康检查 `{status:"ok", time}` |
| GET | `/api/system/info` | 系统信息（Python/平台/主机/CPU/运行时长/插件数） |
| GET | `/api/system/menus` | 聚合菜单（系统 + 插件） |
| GET | `/api/system/time` | 配置时区的当前时间（含 UTC 对照） |
| GET | `/api/system/basic-settings` | 获取基础设置 |
| PUT | `/api/system/basic-settings` | 保存基础设置（软件名/版本/TOTP/自动退出/时区/HTTPS 域名） |
| POST | `/api/system/https/cert` | 上传自定义 HTTPS 证书与私钥（`.crt/.pem` + `.key`） |
| POST | `/api/system/https/switch` | 启停 HTTPS（重启生效） |
| PUT | `/api/system/log-level` | 修改日志级别（落盘，重启保持） |
| GET | `/api/system/log-level` | 获取当前日志级别 |
| POST | `/api/system/session/reset` | 重置当前会话 |
| GET | `/api/system/session/status` | 获取会话剩余时间 |

## 插件（/api/plugins）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/plugins/` | 插件状态列表（name/status/enabled/route_count 等） |
| POST | `/api/plugins/{name}/toggle` | 启用/禁用插件 `{enabled?}`。更新 `user_config.yaml` 并热重载 + 补挂路由 |
| POST | `/api/system/plugins/reload` | 热重启单个插件 `{name}` |
| POST | `/api/system/plugins/reload-all` | 热重启全部插件 |
| POST | `/api/system/plugins/reload-failed` | 仅重启失败插件 |

## 其他（核心静态 / 插件）

- `GET /api/plugins/frontend-manifest`：返回各插件 `frontend/*.js` 清单（带 `?v=<mtime>` 防缓存）。
- `GET /api/wiki/doc/{name}`：读取内置 `wiki/` 文档（需登录，防路径穿越）。
- 静态资源：`/assets`（前端）、`/wiki`（知识库）、`/plugin-assets/<name>/`（插件前端）。

## 鉴权示例

```bash
# 1. 获取加密密钥（明文传输，用于前端加密登录凭据）
curl https://host:port/api/system/crypto-key

# 2. 登录（password 为 AES-256-GCM 加密后的密文；此处简化示意）
curl -X POST https://host:port/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<encrypted>"}'

# 3. 携带 token 调用受保护接口
curl https://host:port/api/plugins/ \
  -H 'Authorization: Bearer <token>'
```
