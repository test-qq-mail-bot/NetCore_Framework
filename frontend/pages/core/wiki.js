// 路径: /wiki/view/<doc>
// 使用文档（原 WikiView）
// 主要功能：按路由文档名渲染 wiki 目录下的文档内容。
// 刷新逻辑：监听 $root.currentPath 变化时重新 fetch API（不依赖 location.reload）。
// 关键接口：静态资源由 /wiki 挂载提供，文档列表由后端插件返回。
window.NC.registerPage('core_wiki', {
    template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">{{title}}</h2>
        <div class="nc-table-card">
          <pre style="white-space:pre-wrap;background:var(--nc-surface-2);padding:12px;border-radius:6px;margin:0;">{{content}}</pre>
        </div>
      </div>
    </div>`,
    data() { return { content: '', title: '' }; },
    methods: {
        async load() {
            const raw = this.$root.currentPath.split('/wiki/view/')[1] || '';
            // 浏览器 location.pathname 可能已对中文做百分号编码，先解码还原真实文件名，
            // 再统一 encodeURIComponent 传给后端（后端会 unquote 一次），避免双重编码导致找不到文件。
            let name = raw;
            try { name = decodeURIComponent(raw); } catch (e) {}
            this.title = name;
            try { const r = await http.get('/api/wiki/doc/' + encodeURIComponent(name)); this.content = r.data; }
            catch (e) { this.content = '文档加载失败'; }
        }
    },
    mounted() { this.load(); },
    watch: { '$root.currentPath'() { this.load(); } }
}, '使用文档');
