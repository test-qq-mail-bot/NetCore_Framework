/* =====================================================================
 * app.js - NetCore Framework 前端布局壳（不含任何业务页面）
 *
 * 职责：
 *  - 登录流程（依赖 NC_HTTP / NC_aesEncrypt / NC_CRYPTO_KEY / NC_zhCn）
 *  - 整体布局（侧边栏 + 内容区 + 头部时钟）
 *  - 菜单渲染与路由（path -> 页面 id，页面由 window.NC.PAGES 注册）
 *  - 错误边界：每个页面用 <nc-error-boundary> 包裹，单页故障不影响其他界面
 *  - 插件前端动态装载：启动时拉取 /api/plugins/frontend-manifest 注入脚本
 *
 * 业务页面分散在：frontend/pages/core/*.js（框架原生页）
 *                 plugins/<name>/frontend/*.js（插件页，见 wiki/05-插件开发指南.md）
 * ===================================================================== */
const { createApp } = Vue;
const http = window.NC_HTTP;
const NC = window.NC;

/* ===================== 登录页 ===================== */
const LoginPage = {
    template: `
    <div class="nc-login-wrap">
      <div class="nc-login-box">
        <div class="nc-login-brand">
          <span class="nc-login-logo"><svg viewBox="0 0 24 24"><path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4z"></path></svg></span>
          <div>
            <h1 class="nc-login-title">{{appName || 'NetCore Framework'}}</h1>
            <p class="nc-login-sub">统一网络设备配置与资产管理平台</p>
          </div>
        </div>
        <el-form @submit.prevent="doLogin" label-width="0">
          <el-form-item>
            <el-input v-model="username" placeholder="用户名" size="large" clearable>
              <template #prefix><svg viewBox="0 0 24 24" class="nc-il-ico"><circle cx="12" cy="8" r="4"></circle><path d="M4 21c0-4 3.5-6 8-6s8 2 8 6"></path></svg></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="password" type="password" placeholder="密码" size="large" show-password @keyup.enter="doLogin">
              <template #prefix><svg viewBox="0 0 24 24" class="nc-il-ico"><rect x="4" y="10" width="16" height="10" rx="2"></rect><path d="M8 10V7a4 4 0 0 1 8 0v3"></path></svg></template>
            </el-input>
          </el-form-item>
          <el-form-item v-if="totpRequired">
            <el-input v-model="totp" placeholder="TOTP 验证码" size="large" @keyup.enter="doLogin">
              <template #prefix><svg viewBox="0 0 24 24" class="nc-il-ico"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"></path></svg></template>
            </el-input>
          </el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="doLogin">登 录</el-button>
        </el-form>
        <div v-if="isDefault" class="nc-tip">提示：当前使用默认密码，建议尽快修改。</div>
      </div>
    </div>`,
    data() { return { username: '', password: '', totp: '', totpRequired: false, isDefault: false, loading: false, appName: '' }; },
    methods: {
        async doLogin() {
            this.loading = true;
            try {
                // 用户名同样要加密：后端 core/api.py 对 username / password / totp 统一走
                // decrypt_field()。若此处明文提交，后端解密失败会回退明文并输出
                // 「字段解密失败」告警（明文 admin 被当 base64 解），同时用户名明文过网。
                const encUser = await window.NC_aesEncrypt(this.username);
                const encPwd = await window.NC_aesEncrypt(this.password);
                const encTotp = this.totp ? await window.NC_aesEncrypt(this.totp) : '';
                const res = await http.post('/api/auth/login', { username: encUser, password: encPwd, totp: encTotp });
                const d = res.data;
                if (d.success) {
                    window.NC_TOKEN = d.token;
                    this.$root.onLoggedIn(d);
                } else {
                    this.$message.error(d.message || '登录失败');
                    if (d.totp_required) this.totpRequired = true;
                }
            } catch (e) {
                this.$message.error('登录异常');
            } finally {
                this.loading = false;
            }
        }
    },
    mounted() {
        http.get('/api/system/crypto-key').then(r => {
            window.NC_CRYPTO_KEY = r.data.key;
            this.appName = r.data.name || 'NetCore Framework';
            this.totpRequired = !!r.data.totp_enabled;
        }).catch(() => {});
    }
};

/* 将 path 映射到已注册的页面 id（框架核心页固定映射，插件页按约定自动推导） */
function resolvePageId(path) {
    path = (path || '/').split('?')[0];

    // ① 显式映射（仅极少数约定推导失败的例外，如 /cmdb/it-assets → cmdb_it）
    if (NC.PATH_MAP[path]) return NC.PATH_MAP[path];

    // ② 框架核心页（固定不变，内建于框架）
    if (path === '/' || path === '/dashboard') return 'core_dashboard';
    if (path === '/system/basic-settings') return 'core_basic';
    if (path === '/system/security') return 'core_security';
    if (path === '/system/notify') return 'core_notify';
    if (path === '/system/log-center') return 'core_logs';
    if (path === '/system/plugins') return 'core_plugins';
    if (path.startsWith('/wiki/view/')) return 'core_wiki';

    // ③ 约定推导：/plugin/page → plugin_page（自动适配所有插件，无需改 app.js）
    //   /guardian/devices → guardian_devices
    //   /opstoolbox/connectivity → opstoolbox_connectivity
    //   /cmdb/dashboard → cmdb_dashboard
    const id = path.slice(1).replace(/\//g, '_');
    if (NC.PAGES[id]) return id;

    return 'core_dashboard'; // 404 兜底
}

/* ===================== 根组件（壳） ===================== */
const App = {
    components: { LoginPage, NcErrorBoundary: NC.ErrorBoundary },
    data() {
        return {
            loggedIn: false,
            username: 'admin',
            isDefaultPassword: false,
            menus: [],
            currentPath: location.pathname || '/dashboard',
            collapsed: false,
            mobileOpen: false,
            appName: '',
            appVersion: '',
            expanded: {},
            sidebarWidth: 220,
            isResizing: false,
            currentTime: '',
            pagesVersion: 0,
            // —— 自动退出（空闲超时）相关状态 ——
            autoLogoutMinutes: 5,   // 0 = 关闭；>0 = 分钟；来自基础设置
            lastActivity: Date.now(),
            lastHeartbeat: 0,
            _idleTimer: null,
            _heartbeatPending: false,
            _onActivity: null,
        };
    },
    computed: {
        // 必须依赖 pagesVersion。插件前端清单是异步加载的，若直接访问/刷新
        // 插件页面 URL（如 /guardian/devices），首次求值时 NC.PAGES 里还没有该页 → 落到
        // core_dashboard 兜底并被 Vue 缓存；清单加载完 pagesVersion++ 后若不作为依赖，
        // 计算属性不会重算，页面会一直停在「系统概览」。
        currentComponent() { void this.pagesVersion; return resolvePageId(this.currentPath); },
        currentPageTitle() {
            return this.findMenuTitle(this.menus, this.currentPath) || (NC.TITLES[this.currentComponent] || this.currentPath);
        },
        // 以下两个在 JS 上下文用 window.NC 取值，避免模板里裸用 NC（Vue 渲染代理不会回退到 window 全局）
        pageRegistered() {
            void this.pagesVersion;
            return !!(this.currentComponent && window.NC && window.NC.PAGES && window.NC.PAGES[this.currentComponent]);
        },
        registeredPageList() {
            try { return Object.keys(window.NC.PAGES).join(', '); } catch (e) { return '(无)'; }
        }
    },
    methods: {
        async onLoggedIn(data) {            this.loggedIn = true;
            this.username = data.username || 'admin';
            // 兼容 snake_case (后端) 和 camelCase (前端约定)
            this.isDefaultPassword = !!(data.isDefaultPassword || data.is_default_password);
            await this.fetchMenus();
            await this.fetchCoreConfig();
            this.loadLogLevel();
            // 统一插件版本号：从后端 /api/plugins/ 拉取并盖章各页面 jsVersions
            if (window.NC && NC.loadPluginVersions) { try { await NC.loadPluginVersions(); } catch (e) {} }
            if (!this.menus.length) this.currentPath = '/dashboard';
            else this.navigate('/dashboard');
            this.startIdleWatcher();
        },
        // 登录与刷新（restoreSession）两条路径都要调用，否则刷新后 DEBUG 输出会失效。
        loadLogLevel() {
            try {
                http.get('/api/system/log-level')
                    .then(function (lr) { try { window.NC_LOG_LEVEL = (lr && lr.data && lr.data.level) || 'INFO'; } catch (e) {} })
                    .catch(function () {});
            } catch (e) {}
        },
        async fetchMenus() { const r = await http.get('/api/system/menus'); this.menus = r.data.menus; },
        async fetchCoreConfig() {
            try {
                const r = await http.get('/api/system/info');
                this.appName = r.data.name || 'NetCore Framework';
                this.appVersion = r.data.version || '';
                document.title = (this.appName || 'NetCore Framework') + (this.appVersion ? ' ' + this.appVersion : '');
            } catch (e) {}
        },
        navigate(path) { history.pushState({}, '', path); this.currentPath = path; this.mobileOpen = false; window.scrollTo(0, 0); this.registerActivity();
            if (window.NC_LOG_LEVEL === 'DEBUG' && window.NC_dbg) {
                var _cid = resolvePageId(path);
                var _title = this.findMenuTitle(this.menus, path) || (window.NC.TITLES && window.NC.TITLES[_cid]) || path;
                console.log(window.NC_dbg('module', '模块切换: ' + _title + ' (' + _cid + ')'));
            }
        },
        goBack() { if (window.history.length > 1) history.back(); else this.navigate('/dashboard'); },
        toggleMenu() {
            if (window.innerWidth <= 768) this.mobileOpen = !this.mobileOpen;
            else this.collapsed = !this.collapsed;
        },
        findMenuTitle(menus, path) {
            if (!menus) return '';
            for (var i = 0; i < menus.length; i++) {
                var m = menus[i];
                if (m.path && m.path === path) return m.label;
                if (m.children && m.children.length) {
                    var t = this.findMenuTitle(m.children, path);
                    if (t) return t;
                }
            }
            return '';
        },
        onContentClick() {
            if (window.innerWidth <= 768 && this.mobileOpen) this.mobileOpen = false;
        },
        // ===================== 自动退出（空闲超时） =====================
        async loadAutoLogoutSetting() {
            try {
                const r = await http.get('/api/system/basic-settings');
                let v = parseInt(r.data && r.data.auto_logout_minutes, 10);
                if (isNaN(v) || v < 0) v = 5;
                this.autoLogoutMinutes = v;
                // 缓存时区到全局变量供 fmtTime 使用（需求2：前端按 user_config.yaml timezone 显示）
                window.NC_TIMEZONE = (r.data && r.data.timezone) || 'Asia/Shanghai';
            } catch (e) {}
        },
        registerActivity() {
            this.lastActivity = Date.now();
            this._heartbeatPending = true;
        },
        checkIdle() {
            if (this.autoLogoutMinutes <= 0) return; // 关闭自动退出
            const idleMs = Date.now() - this.lastActivity;
            if (idleMs >= this.autoLogoutMinutes * 60000) {
                this.doAutoLogout();
                return;
            }
            // 节流心跳：有活动且距上次心跳 >= 20s 才续期后端
            if (this._heartbeatPending && (Date.now() - this.lastHeartbeat) >= 20000) {
                this.lastHeartbeat = Date.now();
                this._heartbeatPending = false;
                this.sendHeartbeat();
            }
        },
        sendHeartbeat() {
            // 静默续期；若已 401 由全局拦截器处理（清 token + 回登录页）
            http.post('/api/auth/heartbeat').catch(function () {});
        },
        doAutoLogout() {
            this.stopIdleWatcher();
            console.warn('[NC] 空闲超时，自动退出登录');
            // 空闲超时同样中断 Telnet/SSH 终端连接（全局清理回调）
            if (window.NC && typeof window.NC.termCleanup === 'function') { try { window.NC.termCleanup(); } catch (e) {} }
            http.post('/api/auth/logout').catch(function () {});
            window.NC_TOKEN = '';
            // 核心修复：直接 SPA 内部回到登录视图，避免整页重载导致插件/轮询重挂
            // 引发的刷新风暴（与 401 拦截器协同，彻底消除狂刷新）。
            this.loggedIn = false;
            this.menus = [];
            this.currentPath = '/dashboard';
        },
        // 收到全局 401 事件（由 framework.js 拦截器派发）：清除会话态并切回登录视图。
        // 与「整页 reload」相比，这种方式不会打断当前上下文、不会重挂轮询组件，
        // 因此即便某个受保护接口瞬时 401，也不会陷入刷新死循环。
        _onUnauthorized() {
            this.stopIdleWatcher();
            // 会话失效（超时/被踢）时中断 Telnet/SSH 终端连接
            if (window.NC && typeof window.NC.termCleanup === 'function') { try { window.NC.termCleanup(); } catch (e) {} }
            window.NC_TOKEN = '';
            this.loggedIn = false;
            this.menus = [];
            this.currentPath = '/dashboard';
        },
        startIdleWatcher() {
            this.stopIdleWatcher();
            this.lastActivity = Date.now();
            this.lastHeartbeat = 0;
            this._heartbeatPending = false;
            this.loadAutoLogoutSetting();
            const self = this;
            this._onActivity = function (e) {
                // keydown 仅当焦点在输入框时计入（鼠标移动/普通按键不刷新）
                if (e && e.type === 'keydown') {
                    const t = e.target;
                    const tag = t && t.tagName;
                    if (!(tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable))) return;
                }
                self.registerActivity();
            };
            document.addEventListener('click', this._onActivity);
            document.addEventListener('keydown', this._onActivity);
            this._idleTimer = setInterval(function () { self.checkIdle(); }, 1000);
        },
        stopIdleWatcher() {
            if (this._idleTimer) { clearInterval(this._idleTimer); this._idleTimer = null; }
            if (this._onActivity) {
                document.removeEventListener('click', this._onActivity);
                document.removeEventListener('keydown', this._onActivity);
                this._onActivity = null;
            }
        },
        _onSettingsChanged() { this.loadAutoLogoutSetting(); },
        async logout() { this.stopIdleWatcher(); if (window.NC && typeof window.NC.termCleanup === 'function') { try { window.NC.termCleanup(); } catch (e) {} } try { await http.post('/api/auth/logout'); } catch (e) {} window.NC_TOKEN = ''; this.loggedIn = false; this.menus = []; },
        async restoreSession() {
            try {
                await this.fetchMenus();
                await this.fetchCoreConfig();
                this.loadLogLevel();
                this.loggedIn = true;
                var p = location.pathname || '/dashboard';
                if (p === '/' || p === '') p = '/dashboard';
                this.currentPath = p;
                this.startIdleWatcher();
            } catch (e) {}
        },
        renderMenu(m, depth) {
            depth = depth || 0;
            var hasChildren = m.children && m.children.length;
            var isOpen = !!this.expanded[m.id];
            var isLeaf = !hasChildren;
            var active = (isLeaf && (m.path || '#') === this.currentPath) ? ' active' : '';
            var cls = 'nc-menu-item'
                + (depth > 0 ? ' nc-sub-depth-' + Math.min(depth, 3) : '')
                + (hasChildren ? ' nc-group' : '')
                + (isOpen ? ' nc-open' : '')
                + active;
            var html = '<div class="' + cls + '"'
                // 审查修复：m.id / m.path 由插件菜单数据提供，拼入 HTML 属性前必须转义，
                // 否则含引号的值可闭合属性注入事件处理器（XSS 纵深防御）
                + (hasChildren ? ' data-toggle="' + this._esc(m.id) + '"' : ' data-path="' + this._esc(m.path || '#') + '"')
                + '>';
            html += '<span class="nc-menu-icon">' + window.NC_iconSvg(m.icon) + '</span>';
            html += '<span class="nc-menu-label">' + this._esc(m.label) + '</span>';
            if (hasChildren) html += '<span class="nc-chevron' + (isOpen ? ' open' : '') + '">' + window.NC_ICONS['chevron'] + '</span>';
            html += '</div>';
            if (hasChildren && isOpen) {
                for (var i = 0; i < m.children.length; i++) html += this.renderMenu(m.children[i], depth + 1);
            }
            return html;
        },
        _esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; },
        onMenuClick(evt) {
            var target = evt.target.closest('.nc-menu-item');
            if (!target) return;
            var toggle = target.getAttribute('data-toggle');
            if (toggle) {
                this.expanded[toggle] = !this.expanded[toggle];
                this.expanded = Object.assign({}, this.expanded);
                return;
            }
            var path = target.getAttribute('data-path');
            if (path && path !== '#') this.navigate(path);
        },
        // 将已注册的页面注册为全局 Vue 组件，供 <component :is="id"> 渲染
        registerAllPages(app) {
            for (var id in NC.PAGES) {
                if (!app._context.components[id]) app.component(id, NC.PAGES[id]);
            }
        },
        // 启动后拉取插件前端清单，动态注入 <script>，实现插件网页留在插件文件夹
        async loadPluginFrontends(app) {
            try {
                // 审查修复：清单接口实际挂了 get_current_user（需已登录会话），
                // 原注释「公开接口」与实现不符，已更正。
                // 偶发的网络抖动/在途中断(ECONNABORTED) 通过一次重试吸收，
                // 避免在控制台刷出无害告警。
                let r = null;
                try {
                    r = await http.get('/api/plugins/frontend-manifest');
                } catch (e1) {
                    await new Promise(res => setTimeout(res, 500));
                    r = await http.get('/api/plugins/frontend-manifest');
                }
                const list = (r && r.data) || [];
                // 清单已按文件 mtime 自带 ?v=，直接使用（插件 JS 一改即失效缓存）；
                // 兼容旧清单（不带查询串）时回退到全局版本号
                const _ncv = '';
                for (const p of list) {
                    for (const f of (p.files || [])) {
                        await new Promise((res) => {
                            const s = document.createElement('script');
                            s.src = f + (f.indexOf('?') >= 0 ? '' : ('?v=' + _ncv));
                            s.onload = () => res(); s.onerror = () => res();
                            document.head.appendChild(s);
                        });
                    }
                }
                this.registerAllPages(app);
                this.pagesVersion++;
            } catch (e) {
                // 即便清单拉取彻底失败，也仅降级提示，绝不阻塞框架与其他页面
                console.info('[NC] 插件前端清单加载失败（不影响框架与核心页面）：', e && (e.message || e));
            }
        }
    },
    watch: {
        currentComponent(v) {
            try { window.__NC_CURRENT_PAGE = v || ''; } catch (e) {}
            if (window.NC_dbg && v) {
                try {
                    const _jv = (window.NC && window.NC.jsVersions) || {};
                    const _ver = _jv[v] || '(未盖章：可能加载旧版 JS，请按 Ctrl+F5 强制刷新)';
                    console.info(window.NC_dbg('app', '[NC] 当前页面 ' + v + ' JS 版本：' + _ver));
                } catch (e2) { /* ignore */ }
            }
        }
    },
    mounted() {
        window.addEventListener('popstate', () => { this.currentPath = location.pathname; });
        window.addEventListener('nc-settings-changed', this._onSettingsChanged);
        // 监听全局 401 事件：切回登录视图（核心修复：替代旧的无脑整页 reload）
        window.addEventListener('nc-unauthorized', this._onUnauthorized);
        http.get('/api/system/crypto-key').then(r => { window.NC_CRYPTO_KEY = r.data.key; }).catch(() => {});
        if (window.NC_TOKEN) this.restoreSession();
        // 兜底：若 401 事件在监听器挂载前已触发（如首屏 restoreSession 时令牌已失效），
        // 通过全局标记直接回到登录视图，避免遗漏导致停留在已失效的会话中。
        if (window.__NC_UNAUTHORIZED__) this._onUnauthorized();
        var self = this;
        function updateTime() {
            var d = new Date();
            self.currentTime = d.getFullYear() + '-' +
                String(d.getMonth() + 1).padStart(2, '0') + '-' +
                String(d.getDate()).padStart(2, '0') + ' ' +
                String(d.getHours()).padStart(2, '0') + ':' +
                String(d.getMinutes()).padStart(2, '0') + ':' +
                String(d.getSeconds()).padStart(2, '0');
        }
        updateTime();
        this._clockTimer = setInterval(updateTime, 1000);
        function onMouseDown(e) {
            if (!e.target.closest('.nc-resize-handle')) return;
            e.preventDefault(); self.isResizing = true;
            document.body.classList.add('nc-resizing');
        }
        // rAF 节流：mousemove 高频事件只保留最新坐标，下一帧才更新宽度，消除拖动卡顿
        let _raf = 0;
        function onMouseMove(e) {
            if (!self.isResizing || self.collapsed) return;
            const next = Math.max(64, Math.min(420, e.clientX));
            if (_raf) return;
            _raf = requestAnimationFrame(function () {
                _raf = 0;
                self.sidebarWidth = next;
            });
        }
        function onMouseUp() {
            if (!self.isResizing) return;
            self.isResizing = false; document.body.classList.remove('nc-resizing');
            if (_raf) { cancelAnimationFrame(_raf); _raf = 0; }
        }
        document.addEventListener('mousedown', onMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    },
    beforeUnmount() { if (this._clockTimer) clearInterval(this._clockTimer); this.stopIdleWatcher(); window.removeEventListener('nc-unauthorized', this._onUnauthorized); },
    template: `
    <login-page v-if="!loggedIn"></login-page>
    <div class="nc-layout" v-else>
      <div class="nc-aside" :class="{collapsed:collapsed, 'mobile-open':mobileOpen}" :style="!collapsed ? {width: sidebarWidth + 'px'} : {}" @click="onMenuClick">
        <div class="nc-logo">
          <span class="nc-logo-icon"><svg viewBox="0 0 24 24"><path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6l-8-4z"></path></svg></span>
          <span class="nc-logo-text">{{appName || 'NetCore Framework'}}</span>
        </div>
        <div class="nc-resize-handle" :class="{dragging:isResizing}"></div>
        <div class="nc-aside-menus">
          <div v-for="(m,idx) in menus" :key="idx" v-html="renderMenu(m)"></div>
        </div>
        <div class="nc-aside-footer">版本号：{{appVersion || '—'}}</div>
      </div>
      <div class="nc-main">
        <div class="nc-header">
          <span class="nc-toggle" @click="toggleMenu" title="折叠/展开菜单"><svg viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></span>
          <el-button class="nc-back" size="small" text bg @click="goBack">返回</el-button>
          <span class="nc-header-title">{{currentPageTitle}}</span>
          <span class="nc-header-spacer"></span>
          <span class="nc-header-time"><svg class="nc-h-ico" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>{{currentTime}}</span>
          <el-button size="small" type="danger" plain @click="logout">退出</el-button>
        </div>
        <div class="nc-content" @click="onContentClick">
          <el-alert v-if="isDefaultPassword" type="warning" :closable="false" title="当前使用默认密码，建议尽快修改" style="margin-bottom:12px;"></el-alert>
          <nc-error-boundary :key="currentPath">
            <template v-if="!pageRegistered">
              <el-alert type="warning" :closable="false" show-icon>
                <template #title>页面未注册</template>
                <div style="font-size:12px;color:var(--nc-text-secondary);">
                  路径 <b>{{currentPath}}</b> 对应的页面组件 <b>{{currentComponent}}</b> 不存在。<br/>
                  已注册页面: {{registeredPageList}}
                </div>
              </el-alert>
            </template>
            <!-- 动态组件加 :key="pagesVersion"——插件前端清单
                 异步加载期间存在竞态：currentComponent 可能在「脚本已注册页面、但 registerAllPages
                 尚未把组件注册进 Vue」的窗口求值，解析成原生空标签；此后 pagesVersion++ 重算值
                 相同，computed 缓存不触发重渲染，页面永久空白。key 随 pagesVersion 变化强制重建。 -->
            <component v-else :is="currentComponent" :key="'pg-' + pagesVersion" class="nc-page" :class="'nc-page-' + currentComponent" :data-page-id="currentComponent"></component>
          </nc-error-boundary>
        </div>
      </div>
    </div>`
};

const app = createApp(App);

// 全局错误处理器：捕获所有组件逃逸的错误（兜底 ErrorBoundary）
app.config.errorHandler = function (err, instance, info) {
    var detail = { message: '', stack: '', info: info || '', time: new Date().toISOString(), component: '' };
    if (!err) { detail.message = 'null/undefined error'; }
    else if (typeof err === 'string') { detail.message = err; }
    else if (err && err.message) { detail.message = err.message; detail.stack = err.stack || ''; }
    else { detail.message = String(err); }
    if (instance && instance.$options) detail.component = instance.$options.name || instance.$options.__name || '?';
    console.error('[NC GLOBAL ERROR HANDLER]', JSON.stringify(detail, null, 2));
    // 写入全局变量供诊断
    window.__NC_GLOBAL_ERROR = detail;
    if (!window.__NC_ERRORS) window.__NC_ERRORS = [];
    window.__NC_ERRORS.push(detail);
};

app.use(ElementPlus, { locale: window.NC_zhCn });
if (typeof ElementPlusIconsVue !== 'undefined') {
    for (const [key, comp] of Object.entries(ElementPlusIconsVue)) app.component(key, comp);
}
// 注册框架原生页（已在 index.html 中通过 <script> 预加载到 NC.PAGES）
app.component('LoginPage', LoginPage);
app.component('NcErrorBoundary', NC.ErrorBoundary);
app.component('nc-sf-th', NC.SFTh);
app.component('nc-table', NC.NcTable);
try {
    for (var _id in NC.PAGES) {
        if (!NC.PAGES.hasOwnProperty(_id)) continue;
        var opts = NC.PAGES[_id];
        if (!opts || !opts.template) { console.warn('[NC] Skipping invalid page:', _id); continue; }
        app.component(_id, opts);
    }
    console.log(window.NC_dbg ? window.NC_dbg('app', '[NC] Registered ' + Object.keys(NC.PAGES).length + ' core pages: ' + Object.keys(NC.PAGES).join(','))
        : '[NC] Registered ' + Object.keys(NC.PAGES).length + ' core pages: ' + Object.keys(NC.PAGES).join(','));
    try {
        http.get('/api/system/crypto-key').then(function (r) {
            const bname = (r && r.data && r.data.builtin_name) || 'NetCore Framework';
            const bver = (r && r.data && r.data.builtin_version) || '';
            if (bver) console.info(window.NC_dbg ? window.NC_dbg('app', '[NC] ' + bname + ' 内置版本：' + bver)
                : '[NC] ' + bname + ' 内置版本：' + bver);
            let stale = false;
            const fwVer = (window.NC && window.NC.FRAMEWORK_VERSION) || '';
            if (bver && fwVer && window.NC && window.NC.verLT && window.NC.verLT(fwVer, bver)) stale = true;
            const jv = (window.NC && window.NC.jsVersions) || {};
            for (const k in jv) { if (window.NC.verLT(jv[k], fwVer)) { stale = true; break; } }
            if (stale && window.ElMessage) window.ElMessage.warning('检测到前端资源可能不是最新，请清除浏览器缓存或按 Ctrl+F5 刷新缓存');
        }).catch(function () {});
    } catch (e) { /* ignore */ }
} catch(e) {
    console.error('[NC] FATAL: Component registration failed!', e);
    window.__NC_REG_ERROR = { message: e.message, stack: e.stack };
}

// 启动后装载插件前端（动态注入插件文件夹内的脚本）
// 关键修复：Vue 3 中 app.mount() 的返回值即根组件实例，app._instance 在 mount 后为 undefined。
// 必须持有 mount 的返回值再调用 loadPluginFrontends，否则插件页面永远无法注册。

window.NC.fmtTime = function (v) {
    if (!v) return '—';
    let s = String(v).replace('Z', '');
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2}):(\d{2})/);
    if (!m) return s;
    // 后端入库统一为 UTC，前端按 user_config.yaml 的 timezone 换算显示（需求2）
    const dt = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]));
    if (isNaN(dt.getTime())) return s;
    const tzName = window.NC_TIMEZONE || 'Asia/Shanghai';
    try {
        const parts = new Intl.DateTimeFormat('zh-CN', {
            timeZone: tzName, year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
        }).formatToParts(dt);
        const get = (t) => (parts.find(p => p.type === t) || {}).value || '';
        return get('year') + '-' + get('month') + '-' + get('day') + ' ' + get('hour') + ':' + get('minute') + ':' + get('second');
    } catch (e) { /* 时区无效时回退 UTC 原样 */ }
    const p = n => (n < 10 ? '0' + n : '' + n);
    return dt.getUTCFullYear() + '-' + p(dt.getUTCMonth() + 1) + '-' + p(dt.getUTCDate()) + ' ' +
           p(dt.getUTCHours()) + ':' + p(dt.getUTCMinutes()) + ':' + p(dt.getUTCSeconds());
};

const vm = app.mount('#app');
if (vm && vm.loadPluginFrontends) {
    vm.loadPluginFrontends(app);
}
