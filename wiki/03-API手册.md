# 03-API手册

所有接口统一前缀 `/api`，除特别标注外均需认证。

---

## 1. 认证约定

### 1.1 加密登录（AES-256-GCM）

登录前必须获取加密密钥：

```
GET /api/system/crypto-key
```

响应：
```json
{
  "key": "base64编码的AES密钥",
  "app_name": "NetCore Framework",
  "version": "20260826-V6",
  "totp_enabled": false
}
```

用该密钥对以下字段加密（AES-256-GCM，Base64 编码后提交）：
- `username` — 用户名
- `password` — 密码
- `totp` — TOTP 验证码（如启用）

前端封装见 `/assets/aesgcm.js`。

### 1.2 JWT Bearer Token

登录成功后返回 `token`，后续所有请求放 Header：

```
Authorization: Bearer <token>
```

Token 有效期默认 1440 分钟（24 小时），由 `core.yaml → jwt.expire_minutes` 控制。

心跳续期：前端每 20 秒以上发 `/api/auth/heartbeat` 续期会话。

### 1.3 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

常见 HTTP 状态码：

| 状态码 | 含义 |
| --- | --- |
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 / Token 无效或过期 / 会话超时 |
| 404 | 资源不存在 / IP 被黑名单封禁 |
| 422 | 请求体校验失败 |
| 500 | 服务端内部错误 |

---

## 2. 认证接口 /api/auth

### POST /api/auth/login

登录认证。

**请求体**：
```json
{
  "username": "加密后的用户名",
  "password": "加密后的密码",
  "totp": "加密后的TOTP验证码（如启用TOTP）"
}
```

**成功响应**（200）：
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "username": "admin",
  "is_default_password": false,
  "totp_required": false
}
```

**需要 TOTP 响应**（200）：
```json
{
  "success": false,
  "totp_required": true,
  "message": "请输入TOTP验证码"
}
```

**失败响应**（400/401）：
```json
{
  "success": false,
  "message": "用户名或密码错误"
}
```

**行为说明**：
- 用户名不存在或密码错误统一返回相同错误信息（防枚举）
- 连续失败触发自动封禁（见安全策略）
- 成功后记录 last_login_time / last_login_ip 到 user_config

### POST /api/auth/totp/setup

发起 TOTP 绑定（需已登录）。

**响应**：
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "otpauth_uri": "otpauth://totp/NetCore:admin?secret=...",
  "qrcode": "base64编码的SVG二维码",
  "qrcode_type": "svg"
}
```

**安全说明**：生成的密钥在服务端以 `pending_totp_secret`（加密）暂存，`verify` 仅校验该待绑定密钥，防止客户端回传任意 secret 绑定到自己掌控的密钥。

### POST /api/auth/totp/verify

校验 TOTP 绑定验证码（需已登录）。

**请求体**：
```json
{
  "code": "123456"
}
```

**响应**：
```json
{
  "success": true,
  "message": "TOTP绑定成功"
}
```

**行为说明**：优先使用 setup 阶段服务端暂存的 `pending_totp_secret`，忽略客户端传入的 secret。成功后写入 `totp_secret` 和 `totp_enabled=true`。

### POST /api/auth/logout

注销当前会话（需已登录）。

**响应**：
```json
{
  "success": true,
  "message": "已退出登录"
}
```

### POST /api/auth/heartbeat

心跳续期（需已登录）。前端每 20 秒以上发一次。

**响应**：
```json
{
  "success": true,
  "remaining_seconds": 280
}
```

- `remaining_seconds` = 剩余空闲秒数
- `-1` = 自动退出已关闭（永不超时）

---

## 3. 安全策略接口 /api/security

### GET /api/security/whitelist

获取白名单列表。

**响应**：
```json
[
  {
    "ip": "127.0.0.1",
    "note": "系统初始化-本地管理通道",
    "expires_at": null
  },
  {
    "ip": "10.0.0.0/8",
    "note": "办公网段",
    "expires_at": "2026-12-31T23:59:59Z"
  }
]
```

### POST /api/security/whitelist

添加白名单条目。

**请求体**：
```json
{
  "ip": "192.168.1.100",
  "note": "管理员办公IP",
  "expires_at": null
}
```

**错误**（400）：IP 已在白名单或黑名单中。

### DELETE /api/security/whitelist

移除白名单条目。

**参数**：`ip`（**query 参数**，不是 body）

```
DELETE /api/security/whitelist?ip=192.168.1.100
```

### GET /api/security/blacklist

获取黑名单列表。

**响应**：
```json
[
  {
    "ip": "203.0.113.45",
    "block_until": "2026-08-26T10:30:00Z",
    "reason": "连续5次失败",
    "note": "",
    "fail_count": 5
  }
]
```

- `block_until` 为 UTC ISO 字符串
- `null` = 永久封禁
- 到期后条目自动失效

### POST /api/security/blacklist

手动拉黑 IP。

**请求体**：
```json
{
  "ip": "203.0.113.45",
  "minutes": 60,
  "note": "暴力破解",
  "expires_at": null
}
```

- `minutes` = 封禁分钟数；`0` 或留空 = 永久
- `expires_at` = 条目有效期（可选）

### DELETE /api/security/blacklist

移除黑名单条目。

**参数**：`ip`（**query 参数**）

```
DELETE /api/security/blacklist?ip=203.0.113.45
```

### GET /api/security/failure-policy

获取失败策略配置。

**响应**：
```json
{
  "max_failures": 5,
  "block_minutes": 10,
  "reset_interval_minutes": 30
}
```

### PUT /api/security/failure-policy

保存失败策略。

**请求体**（同上结构）。

---

## 4. 通知接口 /api/notify

### GET /api/notify/channels

获取各渠道状态。

**响应**：
```json
{
  "email": {
    "enabled": true,
    "template": "default",
    "priority": "normal"
  },
  "wechat_work": {
    "enabled": false,
    "template": "default",
    "priority": "normal"
  }
}
```

### POST /api/notify/send

发送通知。

**请求体**：
```json
{
  "title": "安全告警",
  "content": "检测到异常登录",
  "channels": ["email", "dingtalk"],
  "recipients": ["admin@example.com"]
}
```

- `channels` 省略则发全部启用渠道
- 受频率限制约束（同渠道最小间隔 60 秒）

### POST /api/notify/test/{channel}

对指定渠道发送测试消息。

`channel` ∈ `email` / `wechat_work` / `dingtalk` / `feishu`

**响应**：
```json
{
  "success": true,
  "message": "测试邮件已发送"
}
```

### GET /api/notify/config

读取 notify 配置（敏感字段脱敏/密文）。

### PUT /api/notify/config

保存配置，即时生效。

---

## 5. 审计日志接口 /api/logs

### GET /api/logs/audit

分页查询审计日志。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| page | int | 1 | 页码 |
| size | int | 20 | 每页条数（最大 10000） |
| ip | string | - | 按 IP 筛选 |
| result | string | - | 按结果筛选（success/failed） |
| action | string | - | 按操作类型筛选 |
| start_date | string | - | 起始日期 |
| end_date | string | - | 截止日期 |
| sort_by | string | timestamp_utc | 排序字段 |
| sort_order | string | desc | 排序方向（asc/desc） |
| filter_col | string | - | 筛选列名 |
| filter_values | string | - | 筛选值（逗号分隔） |

**响应**：
```json
{
  "records": [
    {
      "timestamp_utc": "2026-08-26T07:36:57.569Z",
      "ip": "127.0.0.1",
      "username": "admin",
      "action": "login_attempt",
      "result": "success",
      "detail": "登录成功"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 20
}
```

> 列表接口返回原始 UTC 时间戳（`timestamp_utc`），展示换算由前端负责。

### GET /api/logs/audit/export

导出审计日志。

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| fmt | string | csv | 导出格式：`csv` 或 `json`（JSONL） |
| limit | int | 20000 | 最大导出条数（≤20000） |

**响应**：
- CSV：首列为 `timestamp`（**已按系统时区换算**，格式 `YYYY-MM-DD HH:MM:SS`）
- JSONL：每行一个 JSON 对象，同样含 `timestamp` 字段

**截断处理**：超过 limit 时响应头 `X-Audit-Truncated: true`，文件末尾追加说明行。

### DELETE /api/logs/audit/clean

清空全部审计记录（**不可恢复**）。

---

## 6. 系统管理接口 /api/system

### GET /api/system/crypto-key（免认证）

获取登录加密密钥。

**响应**：
```json
{
  "key": "base64编码的AES密钥",
  "app_name": "NetCore Framework",
  "version": "20260826-V6",
  "totp_enabled": false
}
```

### GET /api/system/health（免认证）

健康检查。

**响应**：
```json
{
  "status": "ok",
  "time": "2026-08-26T15:36:57Z"
}
```

### GET /api/system/info

获取系统信息（需认证）。

**响应**：
```json
{
  "platform": "Windows-10",
  "python_version": "3.13.5",
  "plugins_loaded": 3,
  "plugins_failed": 0
}
```

### GET /api/system/menus

聚合菜单（核心页 + 全部启用插件菜单）。

**响应**：
```json
[
  {"id": "dashboard", "label": "系统概览", "path": "/dashboard", "icon": "monitor"},
  {"id": "security", "label": "安全策略", "path": "/security", "icon": "shield"},
  {"id": "wiki_docs_home", "label": "使用文档", "path": "/wiki_docs/home", "icon": "document"}
]
```

### GET /api/system/time

服务端权威时间（需认证）。

**响应**：
```json
{
  "timezone": "Asia/Shanghai",
  "local_time": "2026-08-26 23:36:57",
  "utc_time": "2026-08-26T15:36:57Z",
  "offset_seconds": 28800,
  "offset_hours": 8.0
}
```

### GET /api/system/basic-settings

读取基础设置。

### PUT /api/system/basic-settings

保存基础设置（即时生效）。

**请求体**：
```json
{
  "name": "我的运维平台",
  "version": "2.0",
  "timezone": "Asia/Taipei",
  "auto_logout_minutes": 10,
  "auto_update_timezone": true
}
```

### POST /api/system/https/cert

上传自定义证书（multipart/form-data）。

**参数**：
- `cert_file` — 证书文件（`.crt` / `.pem`）
- `key_file` — 私钥文件（`.key`）

PEM 文本落盘到 `user_config.yaml` 的 `https.cert_content` / `https.key_content`。

### POST /api/system/https/switch

启停 HTTPS / 设置跳转端口。

**请求体**：
```json
{
  "enabled": true,
  "auto_redirect": true,
  "redirect_port": 8081
}
```

需重启完全生效。

### GET /api/system/log-level

获取当前日志级别。

### PUT /api/system/log-level

设置日志级别（即时生效）。

**请求体**：
```json
{
  "level": "DEBUG"
}
```

### GET /api/system/session/status

获取会话状态。

### POST /api/system/session/reset

重置会话管理器（谨慎操作）。

---

## 7. 插件管理接口 /api/plugins 与 /api/system/plugins

### GET /api/plugins/

获取插件状态列表。

**响应**：
```json
[
  {
    "name": "wiki_docs",
    "status": "success",
    "enabled": true,
    "route_count": 5,
    "metadata": {
      "name": "wiki_docs",
      "version": "20260826-V1",
      "description": "内置知识库"
    },
    "path": "plugins/wiki_docs"
  }
]
```

### POST /api/plugins/{name}/toggle

启用/禁用插件。

- 省略 body 或 `{"enabled": true}` → 启用
- `{"enabled": false}` → 禁用

热重载 + 补挂路由。

### POST /api/system/plugins/reload

热重启单个插件。

**请求体**：
```json
{
  "name": "wiki_docs"
}
```

### POST /api/system/plugins/reload-all

热重启全部插件。

### POST /api/system/plugins/reload-failed

仅重启失败插件。

### GET /api/plugins/frontend-manifest

获取插件前端脚本清单（需已登录）。

**响应**：
```json
[
  {
    "name": "wiki_docs",
    "files": ["home.js?v=1724678400"]
  }
]
```

文件以 `/plugin-assets/<name>/<file>` 注入页面。

---

## 8. 静态资源与非 /api 路径

| 路径 | 认证 | 说明 |
| --- | --- | --- |
| `/` | 否 | SPA 入口 index.html |
| `/assets/*` | 否 | 前端静态资源（JS/CSS/图片） |
| `/plugin-assets/<plugin>/*` | 否 | 插件静态 JS（免认证，脚本本身不含数据） |
| `/favicon.svg`、`/favicon.ico` | 否 | 站点 SVG 图标 |
| `/docs`、`/openapi.json` | 否 | Swagger 文档（需 `enable_docs: true`） |
| 含扩展名路径 | - | 未匹配 → JSON 404 |
| 其他路径 | - | 回退 index.html 由前端路由接管 |

---

## 9. 行为要点汇总

| 行为 | 说明 |
| --- | --- |
| IP 被封禁期间 | 访问任何接口返回 404（隐藏后台存在） |
| 白名单 IP | 免失败锁定计数，不是防火墙模式 |
| 审计导出时间 | 已换算为配置时区，字段名 `timestamp` |
| 审计列表时间 | 原始 UTC（`timestamp_utc`），前端负责换算 |
| JWT 密钥 | core.yaml `jwt.secret_key` 首次生成后固定，重启不失效 |
| 会话超时 | 仅内存，重启后所有会话失效 |
| 插件路由 | 运行期摘除不支持，禁用后路由保留到重启 |
