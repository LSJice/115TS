<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useConfigStore } from '@/stores/config'
import { configApi } from '@/api/config'

const store = useConfigStore()
const saving = ref<boolean>(false)
const testing = ref<boolean>(false)

const form = reactive({
  tmdb_api_key: '',
  tmdb_language: 'zh-CN',
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_app_token: '',
  feishu_table_id: '',
  feishu_link_column: '链接',
  feishu_code_column: '提取码',
  feishu_remark_column: '备注',
  feishu_poll_interval_minutes: 5,
  telegram_allowed_chat_ids: '' as string | number[],
  telegram_allowed_user_ids: '' as string | number[],
})

function parseIds(v: string | number[]): number[] {
  if (Array.isArray(v)) return v
  if (!v) return []
  return v
    .split(/[,，\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n))
}

function idsToString(v: number[]): string {
  return v.join(', ')
}

async function load() {
  try {
    const c = await store.fetch()
    form.tmdb_api_key = ''
    form.tmdb_language = c.tmdb_language || 'zh-CN'
    form.feishu_app_id = ''
    form.feishu_app_secret = ''
    form.feishu_app_token = ''
    form.feishu_table_id = c.feishu_table_id || ''
    form.feishu_link_column = c.feishu_link_column || '链接'
    form.feishu_code_column = c.feishu_code_column || '提取码'
    form.feishu_remark_column = c.feishu_remark_column || '备注'
    form.feishu_poll_interval_minutes = c.feishu_poll_interval_minutes || 5
    form.telegram_allowed_chat_ids = idsToString(
      c.telegram_allowed_chat_ids || [],
    )
    form.telegram_allowed_user_ids = idsToString(
      c.telegram_allowed_user_ids || [],
    )
  } catch (e: any) {
    ElMessage.error(`加载配置失败：${e.message}`)
  }
}

async function save() {
  saving.value = true
  try {
    const patch: Record<string, any> = {}
    if (form.tmdb_api_key) patch.tmdb_api_key = form.tmdb_api_key
    if (form.tmdb_language) patch.tmdb_language = form.tmdb_language
    if (form.feishu_app_id) patch.feishu_app_id = form.feishu_app_id
    if (form.feishu_app_secret) patch.feishu_app_secret = form.feishu_app_secret
    if (form.feishu_app_token) patch.feishu_app_token = form.feishu_app_token
    if (form.feishu_table_id) patch.feishu_table_id = form.feishu_table_id
    if (form.feishu_link_column) patch.feishu_link_column = form.feishu_link_column
    if (form.feishu_code_column) patch.feishu_code_column = form.feishu_code_column
    if (form.feishu_remark_column) patch.feishu_remark_column = form.feishu_remark_column
    patch.feishu_poll_interval_minutes = Number(form.feishu_poll_interval_minutes)
    patch.telegram_allowed_chat_ids = parseIds(form.telegram_allowed_chat_ids)
    patch.telegram_allowed_user_ids = parseIds(form.telegram_allowed_user_ids)
    await store.save(patch)
    ElMessage.success('已保存到 .env.override，需重启服务生效')
    // 清空敏感字段，避免下次保存重复写入
    form.tmdb_api_key = ''
    form.feishu_app_id = ''
    form.feishu_app_secret = ''
    form.feishu_app_token = ''
  } catch (e: any) {
    ElMessage.error(`保存失败：${e.message}`)
  } finally {
    saving.value = false
  }
}

async function testFeishu() {
  testing.value = true
  try {
    const resp = await configApi.testFeishu()
    if (resp.ok) {
      ElMessage.success(resp.message || '飞书连通正常')
    } else {
      ElMessage.warning(resp.message || '飞书测试失败')
    }
  } catch (e: any) {
    ElMessage.error(`测试失败：${e.message}`)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
        "
      >
        <h3 style="margin: 0">当前配置（脱敏显示）</h3>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-descriptions
        v-if="store.data"
        :column="2"
        border
        style="margin-top: 12px"
      >
        <el-descriptions-item label="TMDB API Key">
          {{ store.data.tmdb_api_key || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="TMDB Language">
          {{ store.data.tmdb_language }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书 App ID">
          {{ store.data.feishu_app_id || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书 App Token">
          {{ store.data.feishu_app_token || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书表格 ID">
          {{ store.data.feishu_table_id || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书轮询间隔（分钟）">
          {{ store.data.feishu_poll_interval_minutes }}
        </el-descriptions-item>
        <el-descriptions-item label="TG 允许的 chat_id">
          {{ (store.data.telegram_allowed_chat_ids || []).join(', ') || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="TG 允许的 user_id">
          {{ (store.data.telegram_allowed_user_ids || []).join(', ') || '（未配置）' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <h3 style="margin-top: 0">更新配置</h3>
      <el-form :model="form" label-width="200px">
        <el-divider content-position="left">TMDB</el-divider>
        <el-form-item label="TMDB API Key">
          <el-input
            v-model="form.tmdb_api_key"
            placeholder="留空表示不修改"
            show-password
          />
        </el-form-item>
        <el-form-item label="TMDB Language">
          <el-input v-model="form.tmdb_language" />
        </el-form-item>

        <el-divider content-position="left">飞书</el-divider>
        <el-form-item label="App ID">
          <el-input v-model="form.feishu_app_id" placeholder="留空表示不修改" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input
            v-model="form.feishu_app_secret"
            placeholder="留空表示不修改"
            show-password
          />
        </el-form-item>
        <el-form-item label="App Token（表格 token）">
          <el-input v-model="form.feishu_app_token" placeholder="留空表示不修改" />
        </el-form-item>
        <el-form-item label="表格 ID">
          <el-input v-model="form.feishu_table_id" />
        </el-form-item>
        <el-form-item label="链接列名">
          <el-input v-model="form.feishu_link_column" />
        </el-form-item>
        <el-form-item label="提取码列名">
          <el-input v-model="form.feishu_code_column" />
        </el-form-item>
        <el-form-item label="备注列名">
          <el-input v-model="form.feishu_remark_column" />
        </el-form-item>
        <el-form-item label="轮询间隔（分钟）">
          <el-input-number
            v-model="form.feishu_poll_interval_minutes"
            :min="1"
            :max="60"
          />
        </el-form-item>

        <el-divider content-position="left">Telegram</el-divider>
        <el-form-item label="允许的 chat_id">
          <el-input
            v-model="form.telegram_allowed_chat_ids"
            placeholder="逗号分隔，例如：123456, -100987654"
          />
        </el-form-item>
        <el-form-item label="允许的 user_id">
          <el-input
            v-model="form.telegram_allowed_user_ids"
            placeholder="逗号分隔"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">
            保存（写入 .env.override）
          </el-button>
          <el-button :loading="testing" @click="testFeishu">
            测试飞书连通
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
