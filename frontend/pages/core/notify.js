// 路径: /system/notify
// 通知管理（原 NotifyPage）
// 主要功能：查看通知渠道状态、配置邮件/Webhook 等渠道、发送测试通知。
// 关键接口：GET /api/notify/channels、GET/PUT /api/notify/config、POST /api/notify/test/{channel}。
window.NC.registerPage('core_notify', {
    mixins: [window.NC.SF_MIXIN],
template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">通知渠道</h2>
        <div class="nc-table-card">
          <el-alert v-if="loadError" type="error" :closable="false" :title="'数据加载失败：' + loadError" style="margin-bottom:12px;"></el-alert>
          <nc-table :data="channels" :columns="cols">
            <template #col-status="{row}"><el-tag :type="row.enabled?'success':'info'">{{row.status}}</el-tag></template>
            <template #col-ops="{row}">
                <el-button size="small" @click="test(row.id)">测试</el-button>
                <el-button size="small" type="primary" @click="edit(row.id)">编辑</el-button>
            </template>
          </nc-table>
        </div>
      </div>
      <el-dialog title="编辑渠道" v-model="show" width="520px">
        <el-form :model="form" label-width="140px">
          <el-form-item label="启用"><el-switch v-model="form.enabled"></el-switch></el-form-item>
          <el-form-item v-if="form.smtp_host!==undefined" label="SMTP 主机"><el-input v-model="form.smtp_host"></el-input></el-form-item>
          <el-form-item v-if="form.smtp_port!==undefined" label="端口"><el-input v-model.number="form.smtp_port"></el-input></el-form-item>
          <el-form-item v-if="form.username!==undefined" label="账号"><el-input v-model="form.username"></el-input></el-form-item>
          <el-form-item v-if="form.password!==undefined" label="密码"><el-input v-model="form.password" placeholder="留空则不修改"></el-input></el-form-item>
          <el-form-item v-if="form.webhook_url!==undefined" label="Webhook"><el-input v-model="form.webhook_url" placeholder="留空则不修改"></el-input></el-form-item>
          <el-form-item v-if="form.secret!==undefined" label="密钥"><el-input v-model="form.secret" placeholder="留空则不修改"></el-input></el-form-item>
          <el-form-item label="默认收件人" v-if="form.default_recipients!==undefined">
            <el-select v-model="form.default_recipients" multiple filterable allow-create style="width:100%;">
              <el-option v-for="r in form.default_recipients" :key="r" :label="r" :value="r"></el-option>
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer><el-button @click="show=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
      </el-dialog>
    </div>`,
    data() { return { channels: [], show: false, form: {}, currentId: '', loadError: '' }; },
    computed: {
        cols() {
            return [
                { label: '渠道', prop: 'name', sortable: true, filterable: true },
                { label: '状态', prop: 'status', sortable: true, filterable: true, slotName: 'col-status' },
                { label: '操作', slotName: 'col-ops' },
            ];
        },
    },
    methods: {
        async load() {
            try { const r = await http.get('/api/notify/channels'); this.channels = r.data.channels; this.loadError = ''; }
            catch (e) { this.loadError = (e && e.message) || '无法连接到服务器'; }
        },
        async test(id) {
            const res = await http.post('/api/notify/test/' + id, {});
            if (res.data.success) this.$message.success('测试成功：' + res.data.message);
            else this.$message.error('测试失败：' + res.data.message);
        },
        async edit(id) {
            const cfg = await http.get('/api/notify/config'); const c = cfg.data[id] || {};
            this.currentId = id; this.form = JSON.parse(JSON.stringify(c));
            if (this.form.default_recipients === undefined) this.form.default_recipients = [];
            this.show = true;
        },
        async save() {
            const all = await http.get('/api/notify/config');
            const data = all.data; data[this.currentId] = this.form;
            await http.put('/api/notify/config', data);
            this.show = false; this.$message.success('已保存'); this.load();
        }
    },
    mounted() { this.load(); }
}, '通知管理');
