// 路径: /system/security
// 安全策略（原 SecurityPage）
// 主要功能：管理 IP 白名单/黑名单、配置登录失败锁定策略。
// 关键接口：GET/POST/DELETE /api/security/whitelist|blacklist、GET/PUT /api/security/failure-policy。
window.NC.registerPage('core_security', {
    mixins: [window.NC.SF_MIXIN],
template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">失败策略</h2>
        <div class="nc-form-card">
          <el-alert v-if="loadError" type="error" :closable="false" :title="'数据加载失败：' + loadError" style="margin-bottom:12px;"></el-alert>
          <el-form :model="policy" label-width="170px" style="max-width:480px;">
            <el-form-item label="最大失败次数"><el-input v-model.number="policy.max_failures"></el-input></el-form-item>
            <el-form-item label="封禁时长(分钟)"><el-input v-model.number="policy.block_minutes"></el-input></el-form-item>
            <el-form-item label="重置间隔(分钟)"><el-input v-model.number="policy.reset_interval_minutes"></el-input></el-form-item>
            <el-button type="primary" @click="savePolicy">保存</el-button>
          </el-form>
        </div>
      </div>
      <div class="nc-section">
        <h2 class="nc-section-title">IP 名单（白名单 / 黑名单）</h2>
        <div class="nc-form-card">
          <el-alert type="info" :closable="false" style="margin-bottom:16px;">
            <template #title>使用说明</template>
            白名单：受信任的 IP（如管理员来源 IP），<b>放行且免除「多次失败锁定」</b>，不会限制其他用户访问。<br/>
            黑名单：命中且处于封禁期内的 IP 将被拒绝访问。<br/>
            建议为管理员 IP 加入白名单，避免其因多次输错密码被锁定；如需限制某 IP 访问则加入黑名单。
          </el-alert>
          <div class="nc-toolbar">
            <el-input v-model="ipInput" placeholder="IP 或 CIDR，如 192.168.1.100 或 10.0.0.0/8" style="width:260px;"></el-input>
            <el-select v-model="ipType" placeholder="类型" style="width:120px;">
              <el-option label="白名单" value="whitelist"></el-option>
              <el-option label="黑名单" value="blacklist"></el-option>
            </el-select>
            <el-input v-if="ipType==='blacklist'" v-model.number="blMin" placeholder="封禁分钟(留空=永久)" style="width:150px;"></el-input>
            <el-input v-model="ipNote" placeholder="说明（可选，如：管理员办公IP）" style="width:240px;"></el-input>
            <el-date-picker v-model="ipExpires" type="date" placeholder="有效期至(可选)" value-format="YYYY-MM-DD"></el-date-picker>
            <el-button type="primary" @click="addIp">添加</el-button>
          </div>
          <nc-table :data="merged" :columns="cols">
            <template #col-type="{row}"><el-tag :type="row.type==='whitelist'?'success':'danger'">{{row.type==='whitelist'?'白名单':'黑名单'}}</el-tag></template>
            <template #col-time="{row}">
                <!-- 口径：本列只有「空值」和「日期时间」两种形态——
                     空=永久（显示空白）；有值=该时间到点后自动解封（按系统时区换算） -->
                <span>{{ row.time_raw ? row.block_until_cn : '' }}</span>
            </template>
            <template #col-status="{row}">
                <el-tag v-if="row.type==='blacklist'" :type="row.ban_state==='active'?'danger':(row.ban_state==='expired'?'info':'warning')">
                  {{row.ban_state==='active'?'封禁中':(row.ban_state==='expired'?'已过期':'永久封禁')}}
                </el-tag>
                <el-tag v-else :type="row.expired?'info':'success'">{{row.expired?'已过期':'有效'}}</el-tag>
            </template>
            <template #col-ops="{row}"><el-button size="small" type="danger" @click="delIp(row)">移除</el-button></template>
          </nc-table>
        </div>
      </div>
    </div>`,
    data() { return { policy: { max_failures: 5, block_minutes: 10, reset_interval_minutes: 30 }, whitelist: [], blacklist: [], ipInput: '', ipType: 'whitelist', blMin: null, ipNote: '', ipExpires: '', loadError: '' }; },
    computed: {
        cols() {
            return [
                { label: '类型', prop: 'type', width: 110, sortable: true, filterable: true, valueMap: { whitelist: '白名单', blacklist: '黑名单' }, slotName: 'col-type' },
                { label: 'IP', prop: 'ip', width: 180, sortable: true, filterable: true },
                { label: '说明', prop: 'note' },
                { label: '封禁/解封时间', prop: 'time_raw', width: 210, sortable: true, filterable: true, valueFormatter: this.fmtTimeRaw, slotName: 'col-time' },
                { label: '状态', prop: 'status_key', width: 110, sortable: true, filterable: true, valueMap: { active: '封禁中', expired: '已过期', permanent: '永久封禁', valid: '有效' }, slotName: 'col-status' },
                { label: '操作', width: 100, slotName: 'col-ops' },
            ];
        },
        merged() {
            const w = (this.whitelist || []).map(e => {
                const ip = typeof e === 'string' ? e : e.ip;
                const note = typeof e === 'string' ? '' : (e.note || '');
                const exp = typeof e === 'string' ? '' : (e.expires_at || '');
                const expired = !!exp && new Date(exp) < new Date();
                return { type: 'whitelist', ip: ip, note: note, expires: exp || '永久', weekday: exp ? window.NC_weekdayCn(exp) : '', expired: expired, time_raw: exp || '', status_key: expired ? 'expired' : 'valid' };
            });
            const b = (this.blacklist || []).map(e => {
                const until = e.block_until || e.expires_at || '';
                const expired = !!until && new Date(until) < new Date();
                const ban_state = until ? (expired ? 'expired' : 'active') : 'permanent';
                let remain = '';
                if (until && !expired) {
                    const diff = new Date(until) - new Date();
                    const mins = Math.floor(diff / 60000);
                    remain = mins >= 60 ? (Math.floor(mins / 60) + '小时' + (mins % 60) + '分') : (mins + '分钟');
                }
                return {
                    type: 'blacklist', ip: e.ip, note: e.note || '',
                    block_until: until, block_until_cn: this.fmtBlockUntil(until),
                    ban_state: ban_state, remain: remain,
                    expires: until || '永久', weekday: until ? window.NC_weekdayCn(until) : '', expired: expired,
                    time_raw: until || '', status_key: ban_state,
                };
            });
            return w.concat(b);
        },
    },
    methods: {
        fmtBlockUntil(iso) {
            // 空=永久：本列以**空白**呈现（口径见模板注释），不产出「永久」等文案；
            // 非空走 NC.fmtTime 按配置时区换算、去 T/Z/毫秒
            if (!iso) return '';
            if (window.NC && window.NC.fmtTime) return window.NC.fmtTime(iso);
            const d = new Date(iso);
            if (isNaN(d.getTime())) return iso;
            const p = n => (n < 10 ? '0' : '') + n;
            return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
        },
        // 封禁/解封时间列表头筛选标签：空值由框架层渲染为"(空)"，此处仅处理非空时间
        fmtTimeRaw(v) {
            return this.fmtBlockUntil(v);
        },
        async load() {
            try {
                const p = await http.get('/api/security/failure-policy'); this.policy = p.data;
                const w = await http.get('/api/security/whitelist'); this.whitelist = w.data;
                const b = await http.get('/api/security/blacklist'); this.blacklist = b.data;
                this.loadError = '';
            } catch (e) { this.loadError = (e && e.message) || '无法连接到服务器'; }
        },
        async savePolicy() { await http.put('/api/security/failure-policy', this.policy); this.$message.success('已保存'); },
        async addIp() {
            if (!this.ipInput) { this.$message.warning('请输入 IP'); return; }
            const minutes = this.blMin ? Number(this.blMin) : 0;  // 留空即 0 = 永久封禁
            try {
                if (this.ipType === 'whitelist') await http.post('/api/security/whitelist', { ip: this.ipInput, note: this.ipNote, expires_at: this.ipExpires });
                else await http.post('/api/security/blacklist', { ip: this.ipInput, minutes: minutes, note: this.ipNote, expires_at: this.ipExpires });
                this.$message.success('已添加');
                this.ipInput = ''; this.blMin = null; this.ipNote = ''; this.ipExpires = '';
                this.load();
            } catch (e) {
                // 后端对重复 IP（同名单或跨名单）返回 400 + message
                const msg = (e.response && e.response.data && e.response.data.message) || '添加失败';
                this.$message.error(msg);
            }
        },
        async delIp(row) {
            if (row.type === 'whitelist') await http.delete('/api/security/whitelist', { data: { ip: row.ip } });
            else await http.delete('/api/security/blacklist', { data: { ip: row.ip } });
            this.load();
        }
    },
    mounted() { this.load(); }
}, '安全策略');
