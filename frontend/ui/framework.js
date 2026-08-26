/* =====================================================================
 * ui/framework.js - NetCore Framework 前端运行地基（必须在 app.js 与各页面之前加载）
 *
 * 职责（详见 wiki/02-UI框架规范.md 与 wiki/05-插件开发指南.md）：
 *  1. 提供全局 axios 实例 + 401 拦截（自动回登录）
 *  2. 提供 AES-256-GCM 字段加密（与后端 CryptoUtils 兼容）
 *  3. 提供中文 locale、SVG 图标、星期等共享工具
 *  4. 提供页面注册表 window.NC.PAGES 与 registerPage() 注册入口
 *  5. 提供错误边界组件，实现「单页故障不影响其他界面」
 *
 * 插件页只需：window.NC.registerPage('guardian_devices', { ... }, '设备管理')
 * 框架会自动将其装载为可路由的 Vue 组件。
 * ===================================================================== */
(function (global) {
    'use strict';

    /* ---------- 1. 认证令牌与加密密钥（全局，供拦截器与登录加密） ---------- */
    let _token = localStorage.getItem('nc_token') || '';
    let _cryptoKey = '';

    Object.defineProperty(global, 'NC_TOKEN', {
        get() { return _token; },
        set(v) { _token = v || ''; if (v) localStorage.setItem('nc_token', v); else localStorage.removeItem('nc_token'); }
    });
    Object.defineProperty(global, 'NC_CRYPTO_KEY', {
        get() { return _cryptoKey; },
        set(v) { _cryptoKey = v || ''; }
    });

    /* ---------- 2. axios 实例 ---------- */
    function _dbgTs() {
        const d = new Date();
        const p = n => (n < 10 ? '0' + n : '' + n);
        return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' +
            p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
    }
    /**
     * 生成带时间/模块前缀的调试消息：`[YYYY-MM-DD HH:MM:SS] [NCDBG] [模块] 内容`
     * @param {string} tag  模块标签（http / app / guardian / opstoolbox ...）
     * @param {string} msg  消息内容
     */
    global.NC_dbg = function (tag, msg) {
        return '[' + _dbgTs() + '] [NCDBG] [' + tag + '] ' + msg;
    };

    const http = axios.create({ withXSRFToken: false, xsrfCookieName: null, xsrfHeaderName: null, withCredentials: false });
    http.interceptors.request.use((cfg) => {
        if (global.NC_TOKEN) cfg.headers.Authorization = 'Bearer ' + global.NC_TOKEN;
        if (global.NC_LOG_LEVEL === 'DEBUG') {
            try {
                const body = cfg.data ? (typeof cfg.data === 'string' ? cfg.data : JSON.stringify(cfg.data)) : '';
                console.log(global.NC_dbg('http', '➤ ' + String(cfg.method || 'GET').toUpperCase() + ' ' + (cfg.url || '') + (body ? ('\n  请求体: ' + body) : '')));
            } catch (e) { /* ignore */ }
        }
        return cfg;
    });
    http.interceptors.response.use((r) => {
        if (global.NC_LOG_LEVEL === 'DEBUG') {
            try {
                const url = (r.config && r.config.url) || '';
                let data = r.data;
                if (typeof data === 'object') { try { data = JSON.stringify(data); } catch (e) { data = String(data); } }
                console.log(global.NC_dbg('http', '⬅ ' + (r.status || '') + ' ' + url + '\n  响应: ' + data));
            } catch (e) { /* ignore */ }
        }
        return r;
    }, (err) => {
        if (global.NC_LOG_LEVEL === 'DEBUG') {
            try {
                const url = (err.config && err.config.url) || '';
                const resp = err.response ? (err.response.data ? JSON.stringify(err.response.data) : err.response.status) : (err.message || err);
                console.log(global.NC_dbg('http', '❌ ' + (err.response ? err.response.status : 'ERR') + ' ' + url + '\n  响应: ' + resp));
            } catch (e) { /* ignore */ }
        }
        // 401 处理：仅清除本地令牌并派发 nc-unauthorized，由主应用 SPA 内部切回登录视图
        // （不可整页 reload——轮询组件会引发 401 刷新风暴）。
        if (err && err.response && err.response.status === 401) {
            global.NC_TOKEN = '';
            // 标记未授权状态，供主应用挂载时兜底检测（避免事件早于监听器触发而丢失）
            global.__NC_UNAUTHORIZED__ = true;
            try {
                global.dispatchEvent(new CustomEvent('nc-unauthorized', {
                    detail: { url: (err.config && err.config.url) || '' }
                }));
            } catch (e) {
                // 极旧浏览器不支持 CustomEvent 时的兜底：仅回首页路径，不做整页 reload
                try { global.history.replaceState({}, '', '/'); } catch (e2) {}
            }
        }
        return Promise.reject(err);
    });
    global.NC_HTTP = http;
    global.http = http; // 兼容页面脚本中直接使用 http 的写法

    /* ---------- 3. AES-256-GCM 加密（兼容后端 CryptoUtils） ---------- */
    function base64ToBytes(b64) {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return bytes;
    }
    async function aesEncrypt(plaintext) {
        if (!global.NC_CRYPTO_KEY) return plaintext;
        if (typeof crypto !== 'undefined' && crypto.subtle) {
            try {
                const keyBytes = base64ToBytes(global.NC_CRYPTO_KEY);
                const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, ['encrypt']);
                const iv = crypto.getRandomValues(new Uint8Array(12));
                const enc = new TextEncoder().encode(plaintext);
                const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, enc);
                const out = new Uint8Array(iv.length + ct.byteLength);
                out.set(iv);
                out.set(new Uint8Array(ct), iv.length);
                let bin = '';
                for (let i = 0; i < out.length; i++) bin += String.fromCharCode(out[i]);
                return btoa(bin);
            } catch (e) { /* 回退 */ }
        }
        if (typeof aesGcmEncrypt === 'function') return aesGcmEncrypt(plaintext, global.NC_CRYPTO_KEY);
        return plaintext;
    }
    global.NC_aesEncrypt = aesEncrypt;

    /* ---------- 4. 中文 locale（Element Plus） ---------- */
    const zhCn = {
        name: 'zh-cn',
        el: {
            colorpicker: { confirm: '确定', clear: '清空' },
            datepicker: {
                now: '此刻', today: '今天', cancel: '取消', clear: '清空', confirm: '确定',
                selectDate: '选择日期', selectTime: '选择时间', startDate: '开始日期', startTime: '开始时间',
                endDate: '结束日期', endTime: '结束时间', prevYear: '上一年', nextYear: '下一年',
                prevMonth: '上个月', nextMonth: '下个月', year: '年',
                month1: '1 月', month2: '2 月', month3: '3 月', month4: '4 月', month5: '5 月', month6: '6 月',
                month7: '7 月', month8: '8 月', month9: '9 月', month10: '10 月', month11: '11 月', month12: '12 月',
                weeks: { sun: '日', mon: '一', tue: '二', wed: '三', thu: '四', fri: '五', sat: '六' },
                months: { jan: '一月', feb: '二月', mar: '三月', apr: '四月', may: '五月', jun: '六月',
                          jul: '七月', aug: '八月', sep: '九月', oct: '十月', nov: '十一月', dec: '十二月' }
            },
            select: { loading: '加载中', noMatch: '无匹配数据', noData: '无数据', placeholder: '请选择' },
            table: { emptyText: '暂无数据', confirmFilter: '筛选', resetFilter: '重置', clearFilter: '全部' },
            upload: { deleteTip: '按 delete 键删除', delete: '删除', preview: '查看图片', continue: '继续上传' },
            pagination: {
                goto: '前往', pagesize: '条/页', total: '共 {total} 条',
                pageClassifier: '页', prev: '上一页', next: '下一页',
                jumper: '前往', page: '页', jumpto: '跳至', jumppage: '页'
            },
            messagebox: { title: '提示', confirm: '确定', cancel: '取消', close: '关闭' }
        }
    };
    global.NC_zhCn = zhCn;

    const WEEK_CN = ['日', '一', '二', '三', '四', '五', '六'];
    function weekdayCn(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return '';
        return '星期' + WEEK_CN[d.getDay()];
    }
    global.NC_weekdayCn = weekdayCn;

    /* ---------- 5. SVG 图标（线性 Feather 风格，非 emoji） ---------- */
    const ICONS = {
        dashboard: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
        setting: '<svg viewBox="0 0 24 24"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>',
        security: '<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        bell: '<svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
        log: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        plugin: '<svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
        guardian: '<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        doc: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        chevron: '<svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>'
    };
    global.NC_ICONS = ICONS;
    global.NC_iconSvg = function (name) { return ICONS[name] || ICONS['dashboard']; };

    /* ---------- 6. 页面注册表 + 错误边界 ---------- */
    const NC = global.NC = global.NC || {};
    NC.PAGES = NC.PAGES || {};      // id -> Vue 组件 options
    NC.TITLES = NC.TITLES || {};    // id -> 标题
    NC.PATH_MAP = NC.PATH_MAP || {}; // path -> id 显式映射（仅约定推导失败时使用）
    // 必须与 core/config_loader.py 的 SYSTEM_VERSION 保持同步（此前硬编码  落后 SYSTEM_VERSION，
    // 导致 verLT 误判、恒提示「请清除缓存」）。。
    NC.FRAMEWORK_VERSION = "20260824-V2";
    NC.jsVersions = NC.jsVersions || {}; // id -> 该模块 JS 版本号（注册时由对应插件基座盖章）
    NC.verLT = function (a, b) {
        // 比较 "YYYYMMDD-Vn" 形式版本号；a 旧于 b 返回 true。无法解析时按字符串比较。
        if (!a) return !!b;
        if (!b) return false;
        const pa = String(a).match(/^(\d{8})-V(\d+)$/), pb = String(b).match(/^(\d{8})-V(\d+)$/);
        if (pa && pb) {
            const da = +pa[1], db = +pb[1];
            if (da !== db) return da < db;
            return +pa[2] < +pb[2];
        }
        return String(a) < String(b);
    };

    // 全局表头组件：排序 SVG 三角形图标 + 筛选 SVG 漏斗图标，表头靠右布局（文字左、图标右，
    // flex space-between）。筛选弹层=列值枚举多选 + 搜索 + 全选/反选 + 重复项/唯一项 +
    // 候选值升/降序（与数通卫士设备列表同款交互）。排序/筛选状态通过 @sort/@filter 事件通知
    // 父组件：前端数组表配合 NC.SF_MIXIN 的 sfApply；后端分页表由页面自行处理（如设备/日志）。
    NC.SFTh = {
        name: 'nc-sf-th',
        props: {
            label: { type: String, default: '' },
            sortKey: { type: String, default: '' },
            filterKey: { type: String, default: '' },
            prop: { type: String, default: '' },
            source: { type: Array, default: null },
            sortDir: { type: String, default: '' },
            filterVals: { type: Array, default: null },
            valueMap: { type: Object, default: null },
            valueFormatter: { type: Function, default: null },
        },
        emits: ['sort', 'filter'],
        data() { return { innerSort: '', innerVals: [], pop: false, search: '', checked: [], optOrder: 'asc' }; },
        computed: {
            dir() { return this.sortDir !== '' ? this.sortDir : this.innerSort; },
            vals() { return this.filterVals ? this.filterVals : this.innerVals; },
            sortTitle() {
                if (!this.sortKey) return '';
                return '排序' + (this.dir ? (this.dir === 'asc' ? '（升序）' : '（降序）') : '');
            },
            options() {
                const src = this.source || [];
                const map = new Map();
                // 点号路径取值（如 metadata.version / metadata.description）
                const getPath = function (obj, prop) {
                    if (!obj || typeof obj !== 'object' || !prop) return undefined;
                    if (prop.indexOf('.') === -1) return obj[prop];
                    let v = obj;
                    for (const seg of String(prop).split('.')) {
                        if (v === null || v === undefined) return undefined;
                        v = v[seg];
                    }
                    return v;
                };
                for (const r of src) {
                    if (r === null || typeof r !== 'object') continue;
                    let v = getPath(r, this.prop);
                    if (v === undefined || v === null) v = '';
                    let label;
                    // 空值统一渲染为"(空)"（如「封禁/解封时间」空=永久，语义上
                    // 以空白呈现）；列定义 valueFormatter 时仅对非空值生效
                    if (v === '') label = '(空)';
                    else if (this.valueFormatter) label = this.valueFormatter(v);
                    else if (this.valueMap && this.valueMap[v] != null) label = this.valueMap[v];
                    else label = String(v);
                    if (!map.has(label)) map.set(label, { value: v, label: label, count: 0 });
                    map.get(label).count += 1;
                }
                const arr = Array.from(map.values());
                const cmp = (a, b) => {
                    const na = Number(a.value), nb = Number(b.value);
                    if (a.value !== '' && b.value !== '' && !isNaN(na) && !isNaN(nb)) return na - nb;
                    return String(a.value).localeCompare(String(b.value), 'zh');
                };
                arr.sort((a, b) => this.optOrder === 'desc' ? -cmp(a, b) : cmp(a, b));
                return arr;
            },
            shownOptions() {
                const q = (this.search || '').trim().toLowerCase();
                if (!q) return this.options;
                return this.options.filter(o => o.label.toLowerCase().includes(q));
            },
        },
        watch: { vals(v) { this.checked = (v || []).slice(); } },
        methods: {
            toggleSort() {
                if (!this.sortKey) return;
                const next = this.dir === '' ? 'asc' : this.dir === 'asc' ? 'desc' : '';
                this.innerSort = next;
                this.$emit('sort', { key: this.sortKey, dir: next });
            },
            openPop() { this.pop = true; this.search = ''; this.checked = this.vals.slice(); this.optOrder = 'asc'; },
            optSort(dir) { this.optOrder = dir; },
            selAll() { this.checked = this.options.map(o => o.value); },
            selInvert() {
                const all = this.options.map(o => o.value);
                this.checked = all.filter(v => !this.checked.includes(v));
            },
            selDup() { this.checked = this.options.filter(o => o.count > 1).map(o => o.value); },
            selUnique() { this.checked = this.options.filter(o => o.count === 1).map(o => o.value); },
            clearFilter() {
                this.checked = [];
                this.innerVals = [];
                this.pop = false;
                if (this.filterKey) this.$emit('filter', { key: this.filterKey, vals: [] });
            },
            applyFilter() {
                this.pop = false;
                this.innerVals = this.checked.slice();
                this.$emit('filter', { key: this.filterKey, vals: this.checked.slice() });
            },
        },
        template: `<div class="nc-sf-th" style="display:flex;align-items:center;justify-content:space-between;gap:4px;min-width:max-content;">
            <span class="nc-sf-label" :style="sortKey ? 'cursor:pointer;white-space:nowrap;overflow:visible;flex-shrink:0;' : 'white-space:nowrap;overflow:visible;flex-shrink:0;'" @click="sortKey ? toggleSort() : null">{{ label }}</span>
            <span class="nc-sf-icons" style="display:inline-flex;align-items:center;gap:2px;flex-shrink:0;">
              <span v-if="sortKey" class="nc-sf-sort" :class="{on:dir!==''}" :title="sortTitle" style="cursor:pointer;display:inline-flex;color:var(--nc-text);" @click.stop="toggleSort">
                <svg viewBox="0 0 16 16" width="12" height="12" :style="dir==='desc' ? 'transform:rotate(180deg);' : ''"><path fill="currentColor" d="M8 11L3 5h10z"/></svg>
              </span>
              <span v-if="filterKey" class="nc-sf-filter" :class="{on:vals.length>0}" :style="vals.length>0 ? 'cursor:pointer;display:inline-flex;color:#409eff;' : 'cursor:pointer;display:inline-flex;color:var(--nc-text);'">
                <el-popover placement="bottom-start" :width="280" trigger="click" v-model:visible="pop" @show="openPop">
                  <template #reference><span @click.stop><svg viewBox="0 0 16 16" width="12" height="12"><path fill="currentColor" d="M1 2.5h14L9.5 9v5l-3 2V9z"/></svg></span></template>
                  <div style="min-width:240px;">
                    <div style="margin-bottom:6px;display:flex;gap:6px;">
                      <el-button size="small" @click="optSort('asc')">升序</el-button>
                      <el-button size="small" @click="optSort('desc')">降序</el-button>
                    </div>
                    <el-input v-model="search" size="small" placeholder="搜索值" clearable style="margin-bottom:6px;"></el-input>
                    <div style="margin-bottom:6px;display:flex;gap:10px;font-size:12px;color:#409eff;cursor:pointer;">
                      <span @click="selAll">全选</span><span @click="selInvert">反选</span>
                      <span @click="selDup">重复项</span><span @click="selUnique">唯一项</span>
                    </div>
                    <div style="max-height:200px;overflow:auto;">
                      <el-checkbox-group v-model="checked" style="display:block;">
                        <el-checkbox v-for="o in shownOptions" :key="o.label" :label="o.value" style="display:block;white-space:nowrap;">{{ o.label }} ({{ o.count }})</el-checkbox>
                      </el-checkbox-group>
                    </div>
                    <div style="margin-top:8px;text-align:right;">
                      <el-button size="small" @click="clearFilter">清除</el-button>
                      <el-button size="small" type="primary" @click="applyFilter">确定</el-button>
                    </div>
                  </div>
                </el-popover>
              </span>
            </span>
          </div>`,
    };
    // 前端数组表通用排序/筛选 mixin：页面组件 `mixins: [window.NC.SF_MIXIN]`，
    // el-table :data 改 `sfApply(数据源)`，表头 nc-sf-th 的 @sort/@filter 接 sfOnSort/sfOnFilter。
    NC.SF_MIXIN = {
        data() { return { sfSort: { key: '', dir: '' }, sfFilter: {} }; },
        methods: {
            // 点号路径取值（metadata.version 等嵌套字段），无路径则直取
            sfPath(obj, prop) {
                if (!obj || typeof obj !== 'object' || !prop) return undefined;
                if (String(prop).indexOf('.') === -1) return obj[prop];
                let v = obj;
                for (const seg of String(prop).split('.')) {
                    if (v === null || v === undefined) return undefined;
                    v = v[seg];
                }
                return v;
            },
            sfOnSort(p) { this.sfSort = { key: (p && p.key) || '', dir: (p && p.dir) || '' }; },
            sfOnFilter(p) {
                const o = Object.assign({}, this.sfFilter);
                if (p && p.vals && p.vals.length) o[p.key] = p.vals.slice();
                else delete o[p.key];
                this.sfFilter = o;
            },
            sfApply(source) {
                // 容错：非数组数据源（如单对象详情表）原样返回，不排序不筛选
                if (!Array.isArray(source)) return source;
                let list = source.slice();
                const f = this.sfFilter;
                for (const k of Object.keys(f)) {
                    const vals = f[k];
                    if (!vals || !vals.length) continue;
                    list = list.filter(r => {
                        let v = (r === null || typeof r !== 'object') ? undefined : this.sfPath(r, k);
                        if (v === undefined || v === null) v = '';
                        return vals.includes(v);
                    });
                }
                if (this.sfSort.key && this.sfSort.dir) {
                    const key = this.sfSort.key, dir = this.sfSort.dir;
                    list.sort((a, b) => {
                        let av = (a === null || typeof a !== 'object') ? '' : this.sfPath(a, key);
                        let bv = (b === null || typeof b !== 'object') ? '' : this.sfPath(b, key);
                        if (av === undefined || av === null) av = '';
                        if (bv === undefined || bv === null) bv = '';
                        let cmp;
                        if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv;
                        else {
                            const na = Number(av), nb = Number(bv);
                            if (av !== '' && bv !== '' && !isNaN(na) && !isNaN(nb)) cmp = na - nb;
                            else cmp = String(av).localeCompare(String(bv), 'zh');
                        }
                        return dir === 'asc' ? cmp : -cmp;
                    });
                }
                return list;
            },
            // 列间联动候选数据源：应用 sfFilter 中除 excludeKey 之外的筛选，返回派生数据，
            // 供 nc-sf-th 的 :source 绑定，实现「类型筛黑名单后，IP 列筛选项只剩黑名单 IP」的递进缩小。
            sfCandidates(source, excludeKey) {
                if (!Array.isArray(source)) return source;
                let list = source.slice();
                const f = this.sfFilter;
                for (const k of Object.keys(f)) {
                    if (k === excludeKey) continue;
                    const vals = f[k];
                    if (!vals || !vals.length) continue;
                    list = list.filter(r => {
                        let v = (r === null || typeof r !== 'object') ? undefined : this.sfPath(r, k);
                        if (v === undefined || v === null) v = '';
                        return vals.includes(v);
                    });
                }
                return list;
            },
        },
    };

    /* ---------- 6.5 统一表格组件 nc-table（方案A） ----------
     * 声明式列定义 → 自动生成表头排序/筛选（nc-sf-th）+ 斑马纹 + 空态 + 分页。
     * 两种模式：
     *  - 前端数组模式（默认）：:data 传全量数组，组件内部 sfApply 排序筛选；
     *    columns 中 sortable/filterable 为 true 的列自动带表头排序/筛选，候选源自动列间联动。
     *  - 后端分页模式：:backend 传 true，:data 传当前页数据，排序/筛选通过
     *    @sort-change / @filter-change 事件上抛，由页面处理后端参数。
     * 列定义（columns）字段：
     *   label / prop / width / minWidth / sortable / filterable / fixed / align /
     *   formatter(v, row) 单元格格式化 / valueMap 值→文案映射（筛选标签同用）/
     *   valueFormatter(v) 表头筛选候选标签格式化 / slotName 自定义单元格插槽名（默认 col-<prop>）/
     *   render 保留字（若提供则用该插槽渲染）
     */
    NC.NcTable = {
        name: 'nc-table',
        props: {
            columns: { type: Array, default: () => [] },
            data: { type: Array, default: () => [] },
            backend: { type: Boolean, default: false },
            // 前端数组 + 客户端分页：组件内部 sfApply 后按 page/pageSize 切片并显示分页器
            clientPaged: { type: Boolean, default: false },
            rowKey: { type: String, default: 'id' },
            emptyText: { type: String, default: '暂无数据' },
            loading: { type: Boolean, default: false },
            pageSize: { type: Number, default: 20 },
            total: { type: Number, default: 0 },
            page: { type: Number, default: 1 },
            stripe: { type: Boolean, default: true },
            border: { type: Boolean, default: true },
            maxHeight: { type: [Number, String], default: '' },
            // 后端分页模式下的排序/筛选受控值
            sortKey: { type: String, default: '' },
            sortDir: { type: String, default: '' },
            filterVals: { type: Object, default: null },
            // 排除筛选候选源字段（联动）——默认用组件内 sfCandidates
            candidateSource: { type: Array, default: null },
            // 多选列（type=selection），事件经 @selection-change 上抛
            selectable: { type: Boolean, default: false },
            // 分页尺寸可切换（clientPaged 模式下生效）
            pageSizes: { type: Array, default: () => [] },
        },
        emits: ['sort-change', 'filter-change', 'page-change', 'selection-change', 'size-change'],
        mixins: [NC.SF_MIXIN],
        data() { return { innerPage: this.page || 1 }; },
        watch: { page(v) { this.innerPage = v || 1; } },
        computed: {
            sorted() {
                if (this.backend) return this.data || [];
                return this.sfApply(this.data || []);
            },
            totalCount() {
                if (this.backend) return this.total || 0;
                if (this.clientPaged) return this.sorted.length;
                return this.sorted.length;
            },
            shown() {
                if (this.clientPaged && !this.backend) {
                    const s = this.pageSize || 20, p = this.innerPage || 1;
                    const start = (p - 1) * s;
                    return this.sorted.slice(start, start + s);
                }
                return this.sorted;
            },
            thead() {
                return (this.columns || []).filter(c => c && c.label);
            },
        },
        methods: {
            // 点号路径取值（metadata.version 等嵌套字段）
            pathGet(row, prop) {
                if (!row || typeof row !== 'object' || !prop) return undefined;
                if (prop.indexOf('.') === -1) return row[prop];
                let v = row;
                for (const seg of String(prop).split('.')) {
                    if (v === null || v === undefined) return undefined;
                    v = v[seg];
                }
                return v;
            },
            colSource(col) {
                if (this.backend) return this.data || [];
                if (this.candidateSource) return this.candidateSource;
                return this.sfCandidates(this.data || [], col.filterKey || col.prop || '');
            },
            cellVal(row, col) {
                if (col.formatter) return col.formatter(this.pathGet(row, col.prop), row);
                const v = this.pathGet(row, col.prop);
                if (col.valueMap && v != null && col.valueMap[v] != null) return col.valueMap[v];
                if (v === undefined || v === null) return '';
                return v;
            },
            onSort(p) {
                if (this.backend) { this.$emit('sort-change', p); }
                else { this.sfOnSort(p); if (this.clientPaged) this.innerPage = 1; }
            },
            onFilter(p) {
                if (this.backend) { this.$emit('filter-change', p); }
                else { this.sfOnFilter(p); if (this.clientPaged) this.innerPage = 1; }
            },
            onPage(p) {
                if (this.clientPaged && !this.backend) { this.innerPage = p; }
                this.$emit('page-change', p);
            },
        },
        template: `
        <div class="nc-table-wrap">
          <el-table :data="shown" :stripe="stripe" :border="border" :max-height="maxHeight || undefined"
                    :empty-text="emptyText" :loading="loading" :row-key="rowKey"
                    @selection-change="e => $emit('selection-change', e)">
            <el-table-column v-if="selectable" type="selection" width="48" fixed="left"></el-table-column>
            <el-table-column v-for="col in thead" :key="col.prop || col.label"
                             :prop="col.prop" :label="col.label" :width="col.width" :min-width="col.minWidth"
                             :fixed="col.fixed" :align="col.align || 'left'">
              <template #header v-if="col.sortable || col.filterable">
                <nc-sf-th :label="col.label" :sort-key="col.sortKey || col.prop"
                          :filter-key="col.filterKey || col.prop" :prop="col.prop"
                          :source="colSource(col)" :value-map="col.valueMap"
                          :value-formatter="col.valueFormatter"
                          :sort-dir="backend ? (sortKey === (col.sortKey || col.prop) ? sortDir : '') : (sfSort.key === (col.sortKey || col.prop) ? sfSort.dir : '')"
                          @sort="onSort" @filter="onFilter"></nc-sf-th>
              </template>
              <template #default="s">
                <slot v-if="col.slotName" :name="col.slotName" :row="s.row" :value="cellVal(s.row, col)">{{ cellVal(s.row, col) }}</slot>
                <span v-else>{{ cellVal(s.row, col) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="backend || clientPaged" class="nc-table-pager" style="margin-top:12px;display:flex;justify-content:flex-end;align-items:center;gap:12px;">
            <el-pagination background :layout="pageSizes.length ? 'total, sizes, prev, pager, next, jumper' : 'total, prev, pager, next'"
                           :total="totalCount" :page-size="pageSize" :page-sizes="pageSizes"
                           :current-page="backend ? page : innerPage" @current-change="onPage"
                           @size-change="s => $emit('size-change', s)"></el-pagination>
            <slot name="pager-extra"></slot>
          </div>
        </div>`,
    };

    /**
     * 页面模板自动注入模块 class，用于 debug / 定位模块位置。
     * ① 模板根元素：加 `nc-module nc-module-<id>` + `data-module="<id>"`；
     * ② 页面内所有 `class="nc-card"`：追加 `nc-module-<id>-card`。
     * 纯字符串级替换，稳定不随 Vue 重渲染丢失；覆盖全部核心页与插件页，无需逐页手改。
     */
    function _injectModuleClass(tpl, id) {
        if (!tpl || typeof tpl !== 'string') return tpl;
        const cls = 'nc-module nc-module-' + id;
        // ① 根元素注入（允许跳过模板开头的 HTML 注释块）
        tpl = tpl.replace(/^([\s\r\n]*(?:<!--[\s\S]*?-->[\s\r\n]*)*<[a-zA-Z][\w-]*)(\s[^>]*?)?(\/?>)/, function (m, open, attrs, close) {
            let attrStr = attrs || '';
            if (/\bclass\s*=\s*"/.test(attrStr)) {
                attrStr = attrStr.replace(/(class\s*=\s*")/, '$1' + cls + ' ');
            } else if (/\bclass\s*=\s*'/.test(attrStr)) {
                attrStr = attrStr.replace(/(class\s*=\s*')/, '$1' + cls + ' ');
            } else {
                attrStr = ' class="' + cls + '"' + attrStr;
            }
            if (!/\bdata-module\s*=/.test(attrStr)) {
                attrStr = attrStr + ' data-module="' + id + '"';
            }
            return open + attrStr + close;
        });
        // ② 页面内 nc-card 追加模块级 class
        tpl = tpl.replace(/class="nc-card"/g, 'class="nc-card ' + cls + '-card"');
        tpl = tpl.replace(/class='nc-card'/g, "class='nc-card " + cls + "-card'");
        return tpl;
    }

    /**
     * 注册插件/框架页面
     * @param {string} id       页面唯一标识，如 'guardian_devices'
     * @param {object} component Vue 组件 options {template, data, methods, ...}
     * @param {string} title    页面标题
     * @param {string} path     可选，URL 路径（如 /cmdb/it-assets）。若不传则按约定自动推导：
     *                           id 形如 'guardian_devices' → 路径 '/guardian/devices'
     *                           id 形如 'opstoolbox_connectivity' → 路径 '/opstoolbox/connectivity'
     */
    // id 前缀 → 插件名（用于统一版本号盖章）
    NC.PLUGIN_BY_PREFIX = {
        guardian_: 'netconfig_guardian', cmdb_: 'cmdb', opstoolbox_: 'ops_toolbox', wiki_: 'wiki_docs',
    };
    // 页面注册时优先用已拉取的插件版本（js=插件=网页 统一版本号）
    NC.pageVersion = function (id) {
        const pre = String(id).split('_')[0] + '_';
        const pname = NC.PLUGIN_BY_PREFIX[pre];
        if (pname && NC.PLUGIN_VERSIONS && NC.PLUGIN_VERSIONS[pname]) return NC.PLUGIN_VERSIONS[pname];
        return NC.FRAMEWORK_VERSION;
    };
    // 登录后从 /api/plugins/ 拉取插件版本，统一盖章 jsVersions（单一真源=后端 plugin.py）
    NC.loadPluginVersions = function () {
        if (!window.http) return Promise.resolve();
        return window.http.get('/api/plugins/').then(function (r) {
            const list = (r && r.data && r.data.plugins) || [];
            const map = {};
            for (const p of list) {
                const md = (p && p.metadata) || {};
                if (p && p.name && md.version) map[p.name] = md.version;
            }
            NC.PLUGIN_VERSIONS = map;
            // 按 id 前缀统一盖章：guardian_* → netconfig_guardian 版本，以此类推
            for (const id of Object.keys(NC.PAGES)) {
                const pre = String(id).split('_')[0] + '_';
                const pname = NC.PLUGIN_BY_PREFIX[pre];
                if (pname && map[pname]) NC.jsVersions[id] = map[pname];
            }
            return map;
        }).catch(function () { return null; });
    };
    NC.registerPage = function (id, component, title, path) {
        if (component && component.template) {
            component.template = _injectModuleClass(component.template, id);
        }
        NC.PAGES[id] = component;
        if (title) NC.TITLES[id] = title;
        if (path) NC.PATH_MAP[path] = id;
        if (!(id in NC.jsVersions)) NC.jsVersions[id] = NC.pageVersion(id);
    };

    // 错误边界：某页面渲染期抛错时，仅显示该页「模块加载失败」，不影响其他界面
    NC.ErrorBoundary = {
        name: 'NcErrorBoundary',
        data() { return { hasError: false, message: '', stack: '', errorType: '', diagHint: '' }; },
        errorCaptured(err) {
            this.hasError = true;
            // 兼容多种错误类型：Error 实例 / axios 错误对象 / 字符串 / null / undefined
            if (!err) {
                this.message = '未知错误（错误对象为空）';
                this.stack = '';
                this.errorType = 'null';
            } else if (typeof err === 'string') {
                this.message = err;
                this.stack = '';
                this.errorType = 'string';
            } else if (err.isAxiosError || (err.config && err.request)) {
                // axios 错误：优先显示网络层信息
                if (err.response) {
                    var status = err.response.status;
                    var data = err.response.data;
                    this.message = '请求失败 [' + status + '] ' + (err.message || '') +
                        (data ? (' — ' + (typeof data === 'string' ? data : JSON.stringify(data).substring(0, 200))) : '');
                } else if (err.request) {
                    this.message = '网络错误：无法连接到服务器（' + (err.message || '连接被拒绝或超时') + '）';
                } else {
                    this.message = err.message || '请求配置错误';
                }
                this.stack = err.stack || '';
                this.errorType = 'axios';
            } else if (err instanceof Error) {
                this.message = err.message || String(err);
                this.stack = err.stack || '';
                this.errorType = 'Error';
            } else {
                this.message = String(err);
                this.stack = '';
                this.errorType = typeof err;
            }
            this.diagHint = '';
            const _m = String(this.message || '');
            if (_m.indexOf('_withMods') !== -1 || _m.indexOf("reading '_withMods'") !== -1) {
                const _pg = (typeof window !== 'undefined' && window.__NC_CURRENT_PAGE) || '';
                this.diagHint = '该错误来自页面模板中的事件绑定：某个 @click.stop / @submit.prevent 等带修饰符的事件'
                    + '没有可用的处理函数（纯修饰符无 handler，或引用的方法未定义/未在 methods 中声明，'
                    + '常见原因：方法被误放在 methods 对象之外）。'
                    + '排查：F12 控制台执行 JSON.stringify(window.NC.PAGES["' + _pg + '"].methods)，'
                    + '核对事件引用的方法是否存在；或在页面 JS 中搜索 @xxx.stop / @submit.prevent。';
            }
            // eslint-disable-next-line no-console
            console.error('[NC] 页面渲染错误（已隔离）：', this.errorType, this.message, err);
            // 暴露到全局供诊断
            if (window) window.__NC_LAST_ERROR = { type: this.errorType, message: this.message, stack: this.stack, time: new Date().toISOString() };
            // 直接写 DOM 兜底（Vue 响应式可能未更新）
            setTimeout(function() {
                var cards = document.querySelectorAll('.nc-error-card');
                for (var i = 0; i < cards.length; i++) {
                    var detail = cards[i].querySelector('.nc-error-detail');
                    if (detail && !detail.hasChildNodes()) {
                        detail.innerHTML = '<b style="color:#f56c6c;">' + (this.message || '(空消息)') + '</b>' +
                            '<span style="margin-left:8px;color:#c0c4cc;">（类型：' + (this.errorType || '?') + '）</span><br/>' +
                            '<pre style="max-height:200px;overflow:auto;font-size:11px;margin-top:4px;background:#fef0f0;padding:6px;border-radius:4px;color:#f56c6c;white-space:pre-wrap;">' +
                            (this.stack || '(无堆栈)') + '</pre>' +
                            '<div style="margin-top:8px;padding:8px;background:#fff3cd;color:var(--nc-text);border-radius:4px;font-size:11px;"><b>诊断提示：</b>请按 F12 打开控制台，运行 <code style="background:#eee;padding:1px 4px;">JSON.stringify(window.__NC_GLOBAL_ERROR, null, 2)</code></div>';
                    }
                }
            }.bind(this), 100);
            return false; // 阻止向上冒泡，避免整个应用崩溃
        },
        template: `<div>
            <div v-if="hasError" class="nc-error-card">
                <el-alert type="error" :closable="false" show-icon>
                    <template #title>模块加载失败</template>
                    <div class="nc-error-detail" style="font-size:12px;color:var(--nc-text);margin-top:4px;word-break:break-all;">
                        该模块发生运行时错误，已隔离，不影响其他界面：<br/>
                        <b style="color:#f56c6c;" v-if="message">{{message}}</b>
                        <span v-else style="color:#f56c6c;">(错误信息为空 — 请查看控制台 __NC_LAST_ERROR)</span>
                        <span v-if="errorType" style="margin-left:8px;color:#c0c4cc;">（类型：{{errorType}}）</span><br/>
                        <div v-if="diagHint" style="margin-top:8px;padding:8px;background:#fff3cd;color:var(--nc-text);border-radius:4px;font-size:11px;line-height:1.6;">
                          <b>诊断提示：</b>{{diagHint}}
                        </div>
                        <pre v-if="stack" style="max-height:200px;overflow:auto;font-size:11px;margin-top:4px;background:#fef0f0;padding:6px;border-radius:4px;color:#f56c6c;">{{stack}}</pre>
                        <pre v-else-if="!message && !stack" style="font-size:11px;margin-top:4px;background:#fff3cd;padding:6px;border-radius:4px;color:var(--nc-text);">
诊断：ErrorBoundary 被触发但错误对象为空。
请打开浏览器控制台(F12)并运行：
  JSON.stringify(window.__NC_LAST_ERROR)
  JSON.stringify(window.__NC_GLOBAL_ERROR)
  JSON.stringify(window.__NC_ERRORS)</pre>
                    </div>
                </el-alert>
            </div>
            <slot v-else></slot>
        </div>`
    };

    // ---------- 7. 全局错误捕获（兜底 ErrorBoundary 之外的错误） ----------
    if (typeof window !== 'undefined') {
        window.__NC_ERRORS = [];
        window.addEventListener('error', function(e) {
            var msg = (e && e.message) || '';
            // 过滤 Element Plus 触发的良性 ResizeObserver 警告（非真实错误，仅在任务页等复杂
            // 表格/弹窗布局下反复刷屏，无需计入错误列表或打印到控制台）
            if (msg && (msg.indexOf('ResizeObserver loop completed with undelivered notifications') !== -1
                || msg.indexOf('ResizeObserver loop limit exceeded') !== -1)) {
                return;
            }
            var info = { message: msg, filename: e.filename, line: e.lineno, col: e.colno, time: new Date().toISOString(), type: 'window.onerror' };
            window.__NC_ERRORS.push(info);
            console.error('[NC Global]', info);
        });
        window.addEventListener('unhandledrejection', function(e) {
            var info = { message: String(e.reason && e.reason.message ? e.reason.message : e.reason), stack: (e.reason && e.reason.stack) || '', time: new Date().toISOString(), type: 'unhandledrejection' };
            window.__NC_ERRORS.push(info);
            console.error('[NC Promise]', info);
        });
    }

    // ---------- 7.1 DEBUG 全局交互追踪（R7：交互元素定位 + 点击/输入反馈） ----------
    // 作用：DEBUG 模式下，记录用户点击/输入的元素「所属模块 + tag + id + class + 文本/内容 + XPath 路径」，
    // 便于复现与定位问题。元素身份由 XPath 唯一确定，无需给每行代码加 class。
    // 监听在 document 捕获阶段统一挂载，处理函数内用 NC_LOG_LEVEL 实时判断，
    // 保证无论日志级别何时从后端拉取生效，都能正确启停（生产模式仅一次属性读取即返回，开销可忽略）。
    function _ncXPath(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el === document.body) return '/body';
        if (el.id) return '//*[@id="' + el.id + '"]';
        var parts = [];
        var node = el;
        while (node && node.nodeType === 1 && node !== document.body) {
            if (node.id) { parts.unshift('//*[@id="' + node.id + '"]'); break; }
            var idx = 1;
            var sib = node.previousElementSibling;
            while (sib) { if (sib.tagName === node.tagName) idx++; sib = sib.previousElementSibling; }
            var total = 1;
            var sib2 = node.nextElementSibling;
            while (sib2) { if (sib2.tagName === node.tagName) total++; sib2 = sib2.nextElementSibling; }
            var pos = (total > 1) ? ('[' + idx + ']') : '';
            parts.unshift(node.tagName.toLowerCase() + pos);
            node = node.parentElement;
        }
        return '/' + parts.join('/');
    }
    function _ncInteractiveOf(el) {
        while (el && el.nodeType === 1) {
            var tag = (el.tagName || '').toLowerCase();
            if (tag === 'button' || tag === 'a' || tag === 'input' || tag === 'select' || tag === 'textarea') return el;
            if (el.getAttribute) {
                var role = el.getAttribute('role');
                if (role === 'button' || role === 'tab' || role === 'menuitem') return el;
            }
            if (el.classList && (el.classList.contains('el-button') || el.classList.contains('el-menu-item') ||
                el.classList.contains('el-tab-pane') || el.classList.contains('nc-interactive'))) return el;
            el = el.parentElement;
        }
        return null;
    }
    function _ncTextOf(el) {
        if (!el) return '';
        var tag = (el.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea') {
            return (el.type === 'password') ? '(password)' : (el.value || '');
        }
        var txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
        return txt.length > 60 ? txt.substring(0, 60) + '…' : txt;
    }
    function _ncElDesc(el) {
        if (!el) return '';
        var tag = (el.tagName || '').toLowerCase();
        var id = el.id ? ('#' + el.id) : '';
        var cls = (el.className && typeof el.className === 'string') ? ('.' + el.className.trim().split(/\s+/).filter(Boolean).join('.')) : '';
        return tag + id + cls;
    }
    function _ncModuleOf(el) {
        try {
            var m = el && el.closest && el.closest('[data-module]');
            return m ? m.getAttribute('data-module') : '';
        } catch (e) { return ''; }
    }
    if (typeof window !== 'undefined') {
        document.addEventListener('click', function (e) {
            if (global.NC_LOG_LEVEL !== 'DEBUG') return;
            try {
                var target = e.target;
                if (!target || !target.nodeType) return;
                var el = _ncInteractiveOf(target) || target;
                var tag = (el.tagName || '').toLowerCase();
                // 文本/密码等输入框的点击不在此记录，由 input 事件负责
                if (tag === 'input' && ['text', 'password', 'search', 'number', 'email', 'tel', ''].indexOf(el.type) !== -1) return;
                if (el.classList) el.classList.add('nc-interactive');
                console.log(global.NC_dbg('click', '点击 [' + _ncModuleOf(el) + '] ' + _ncElDesc(el) +
                    ' 文本="' + _ncTextOf(el) + '" 路径=' + _ncXPath(el)));
            } catch (err) { /* ignore */ }
        }, true);
        document.addEventListener('input', function (e) {
            if (global.NC_LOG_LEVEL !== 'DEBUG') return;
            try {
                var el = e.target;
                if (!el || !el.nodeType) return;
                var tag = (el.tagName || '').toLowerCase();
                if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') return;
                if (el.classList) el.classList.add('nc-interactive');
                var val = (tag === 'input' && el.type === 'password') ? '(password)' : (el.value || '');
                console.log(global.NC_dbg('input', '输入 [' + _ncModuleOf(el) + '] ' + _ncElDesc(el) +
                    ' 内容="' + val + '" 路径=' + _ncXPath(el)));
            } catch (err) { /* ignore */ }
        }, true);
    }

})(window);
