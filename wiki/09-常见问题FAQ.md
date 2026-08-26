# 09-常见问题FAQ

---

## 1. 端口与网络

### Q: 程序在运行但网页打不开

**可能原因**：
1. 防火墙未放行端口（8080 + 跳转端口 8081）
2. 访问地址错误（HTTPS 用 http:// 访问，或反之）
3. 端口被占用，框架自动顺延到了其他端口

**排查步骤**：
1. 看控制台输出的实际监听地址（如 `https://0.0.0.0:8083`）
2. 用实际地址访问
3. 检查防火墙放行规则

### Q: 端口被占用

框架默认端口 8080，被占用时自动顺延 +1 ~ +20。**以控制台打印的实际地址为准**。

固定端口：编辑 `config/core.yaml`：
```yaml
server:
  port: 9000
```

### Q: 8081 端口是什么

反向协议跳转监听端口（HTTP→HTTPS 自动跳转）。用户用 `http://` 访问时自动跳转到 `https://`。

关闭方式：
```yaml
# config/user_config.yaml
https:
  auto_redirect: false
```

---

## 2. 登录与密码

### Q: 默认密码登录失败

默认密码：`admin / Admin@123!`

如果仍失败：
1. 检查是否已被自动封禁（看控制台日志或安全策略页面）
2. 密码哈希损坏：删除 `config/user_config.yaml` 中的 `auth.password_hash` 行，重启，重建为默认密码

### Q: 如何修改密码

1. 编辑 `config/user_config.yaml`
2. 在 `auth:` 段添加：`password_plain: "新密码"`
3. 保存，重启程序
4. 框架自动重置哈希并删除该字段后退出
5. 再次启动，用新密码登录

### Q: TOTP 验证码无效

1. 确认手机 App 时间与服务器同步（NTP）
2. TOTP 校验窗口为 ±1 个周期（30 秒）
3. 如手机丢失：编辑 `user_config.yaml`，设置 `totp_enabled: false`、`totp_secret: ""`，重启

---

## 3. 安全策略

### Q: 自己被锁定了怎么办

1. 用白名单内的 IP 登录（如本机 `127.0.0.1`）
2. 或编辑 `config/security.yaml`，从 `blacklist` 中移除你的 IP 条目
3. 重启生效

### Q: 回环白名单删了又自动回来

V6 之前：每次重启自动补写。V6 起：**仅首次初始化写入，删除即永久生效**。

如果删除后重启没有加回，说明是 V6+ 行为。如需恢复，手动编辑 `security.yaml` 添加：
```yaml
whitelist:
  - ip: "127.0.0.1"
    note: "本地管理通道"
    expires_at: null
```

### Q: 封禁/解封时间列显示"永久"是什么意思

- `永久` = 该条目无到期时间，永久封禁/永久白名单
- 有日期时间 = 到期后自动失效

状态由「状态」列标签承担：封禁中 = 红色；已过期 = 灰色；永久封禁 = 红色。

### Q: 被封禁的 IP 访问返回 404

正常行为。封禁期间访问**任何接口**（包括首页、API、静态资源）都返回 404，不暴露后台存在。

---

## 4. 时间显示

### Q: 时间显示不对 / 带 T、Z、毫秒

全站口径：UTC 入库 + `user_config.yaml → system.timezone` 换算 + `YYYY-MM-DD HH:MM:SS`。

排查：
1. 检查 `system.timezone` 是否正确（基础设置可改）
2. 旧版本可能用 UTC 原样显示，升级到 V6+
3. Windows 下时区换算依赖 tzdata（新版已内置）

### Q: 审计导出的时间还是 UTC

V6 起导出即换算值（字段名 `timestamp`）。如仍为 UTC 请升级。

### Q: Windows 下时区报错

`requirements.txt` 已锁定 `tzdata==2026.3`。确保已安装：
```bash
uv pip install tzdata==2026.3 --python .venv
```

---

## 5. 插件

### Q: 插件菜单出现但接口 404

**可能原因**：
1. 插件路由未挂载（运行期启用后需 `mount_new_routes` 补挂）
2. `get_routes()` 返回了 None 或空 router
3. 插件加载失败（status=failed）

**排查**：
1. 插件管理页检查 route_count 是否为 0
2. 查看日志中 `插件 <name> 加载失败` 的错误信息
3. 重启框架（启动期全量挂载）

### Q: 所有插件页面空白

1. 浏览器 F12 控制台查看错误
2. 检查登录状态（插件脚本注入需已登录会话）
3. 老版本：登录成功后刷新一次（V6+ 自动补拉）

### Q: 新装插件不生效

1. 目录层级必须 `plugins/<name>/plugin.py`，不要多套一层下载仓库文件夹
2. 必须放到**正在运行的那个 exe** 同级 `plugins/` 下
3. 重启框架

### Q: 插件加载失败

查看日志：`logs/YYYYMMDD-netcore.log` 搜索 `插件 <name> 加载失败`。

常见原因：
- 依赖缺失（requirements.txt 未包含）
- `on_load()` 抛异常
- `plugin.py` 中未找到 `BasePlugin` 子类
- 配置文件格式错误

---

## 6. HTTPS

### Q: 浏览器提示"不安全"

自签名证书属正常现象。绕过方式：
- Chrome/Edge：点击「高级」→「继续前往...（不安全）」
- Firefox：点击「高级」→「接受风险并继续」

上传受信任证书可消除告警。

### Q: 证书域名不匹配

配置 `https.domain` 含访问 IP/域名后重启：
```yaml
https:
  domain: "192.168.1.100,myserver.local"
```

### Q: HTTP 访问没跳转

1. 确认 `auto_redirect: true`
2. 确认跳转端口未被占用
3. 检查控制台是否打印了跳转监听地址

---

## 7. 通知

### Q: 通知发送失败

1. 检查渠道 `enabled: true`
2. 检查凭据（SMTP 密码、Webhook URL、钉钉加签密钥）是否正确
3. 「通知管理 → 测试」即时验证
4. 成功与否都写审计日志（action=`notify_test`）
5. 频率限制：同渠道最小间隔 60 秒

### Q: 邮件正文时间还是 UTC

V6 起通知模板 Time 字段已换算为配置时区。如仍为 UTC 请升级。

---

## 8. 升级与数据

### Q: 升级后数据丢失

不应发生。资源提取为「合并拷贝 + 跳过 data/logs/__pycache__」。

如果丢失：
1. 检查是否手工删除过目录
2. 从 `.workbuddy/backup_*` 备份恢复
3. 检查构建脚本是否配置正确

### Q: 如何升级

1. 关闭程序
2. 备份 `config/`、`data/`、`plugins/<name>/data/`（构建脚本自动备份到 .workbuddy）
3. 覆盖新 exe
4. 启动

---

## 9. 日志

### Q: 日志文件在哪里

| 类型 | 位置 |
| --- | --- |
| 运行日志 | `logs/YYYYMMDD-netcore.log` |
| 审计日志 | `data/logs/audit/audit-YYYYMMDD.log` |

### Q: 如何查看实时日志

- 控制台直接输出（跟随日志级别）
- Web 后台「日志中心」查看审计日志
- 运行日志直接看文件或 `tail -f`

### Q: DEBUG 级别日志太大

DEBUG 会输出每个请求的明细。排查完毕后切回 INFO：
- Web 后台「日志中心」热切换
- 或编辑 `user_config.yaml → logging.level: INFO`

---

## 10. 其他

### Q: 客户端断开报 ConnectionResetError

Windows 下客户端正常断开触发 10054 属噪声。框架已在事件循环挂处理器过滤，不影响功能与业务日志。

### Q: 如何清理全部审计日志

Web 后台「日志中心 → 清理」按钮。**不可恢复**。

也可手动删除 `data/logs/audit/audit-*.log`。

### Q: 如何查看已注册的插件页面

浏览器控制台执行：
```javascript
JSON.stringify(Object.keys(window.NC.PAGES))
```

### Q: 如何开启 Swagger 文档

编辑 `config/user_config.yaml`：
```yaml
security:
  enable_docs: true
```

重启后访问 `/docs`。
