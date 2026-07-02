<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tasksApi } from '@/api/tasks'
import type { TaskOut } from '@/types'

const tasks = ref<TaskOut[]>([])
const loading = ref<boolean>(false)
const submitInput = ref<string>('')
const submitting = ref<boolean>(false)
const filterStatus = ref<string[]>([])
const pollTimer = ref<number | null>(null)
let evtSource: EventSource | null = null

const statusOptions = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '处理中', value: 'running' },
  { label: '已完成', value: 'done' },
  { label: '已失败', value: 'failed' },
  { label: '已跳过', value: 'skipped' },
]

const filteredTasks = computed(() => {
  if (filterStatus.value.length === 0) return tasks.value
  return tasks.value.filter((t) => filterStatus.value.includes(t.status))
})

async function fetchTasks() {
  loading.value = true
  try {
    tasks.value = await tasksApi.list({ limit: 100 })
  } catch (e: any) {
    ElMessage.error(`加载任务列表失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function submit() {
  const raw = submitInput.value.trim()
  if (!raw) {
    ElMessage.warning('请粘贴 115 分享链接')
    return
  }
  submitting.value = true
  try {
    const t = await tasksApi.create({ raw_input: raw })
    ElMessage.success(`任务 #${t.id} 已创建`)
    submitInput.value = ''
    await fetchTasks()
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message
    ElMessage.error(`创建失败：${detail}`)
  } finally {
    submitting.value = false
  }
}

async function retry(taskId: number) {
  try {
    await tasksApi.retry(taskId)
    ElMessage.success(`任务 #${taskId} 已重新入队`)
    await fetchTasks()
  } catch (e: any) {
    ElMessage.error(`重试失败：${e.message}`)
  }
}

async function editCategory(t: TaskOut) {
  try {
    const { value: category } = await ElMessageBox.prompt(
      '请输入新分类（电影/电视剧/动漫/综艺/学习/_未分类）',
      `修正任务 #${t.id} 分类`,
      {
        inputValue: t.category || '',
        inputPattern: /.+/,
        inputErrorMessage: '分类不能为空',
      },
    )
    const { value: path } = await ElMessageBox.prompt(
      '目标路径覆盖（可留空使用默认）',
      '目标路径',
      { inputValue: t.target_path || '', inputErrorMessage: '' },
    ).catch(() => ({ value: '' }))
    await tasksApi.updateCategory(t.id, {
      category,
      target_path_override: path || null,
    })
    ElMessage.success('已修正分类并重新入队')
    await fetchTasks()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(`修正失败：${e.message}`)
  }
}

function statusTagType(s: TaskOut['status']) {
  return {
    pending: 'info',
    running: 'warning',
    done: 'success',
    failed: 'danger',
    skipped: 'info',
  }[s]
}

function formatTime(ts: number | null): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

function startSSE() {
  if (evtSource) evtSource.close()
  evtSource = new EventSource('/api/tasks/stream')
  evtSource.addEventListener('task', (e: MessageEvent) => {
    try {
      const evt = JSON.parse(e.data)
      // 收到事件后刷新列表（简单策略）
      fetchTasks()
      if (evt.status === 'done') {
        ElMessage.success(`任务 #${evt.task_id} 已完成`)
      } else if (evt.status === 'failed') {
        ElMessage.error(`任务 #${evt.task_id} 失败：${evt.error || ''}`)
      } else if (evt.status === 'auth_expired') {
        ElMessage.warning('115 登录已失效，请重新扫码')
      }
    } catch (err) {
      console.warn('parse SSE event failed', err)
    }
  })
  evtSource.onerror = () => {
    // SSE 断开后自动重连由浏览器处理；这里仅记录
    console.warn('SSE connection error')
  }
}

function stopSSE() {
  if (evtSource) {
    evtSource.close()
    evtSource = null
  }
}

function startPollingFallback() {
  // 兜底：每 10s 拉一次列表，避免 SSE 偶发断开导致页面不更新
  pollTimer.value = window.setInterval(fetchTasks, 10000)
}

function stopPollingFallback() {
  if (pollTimer.value !== null) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onMounted(() => {
  fetchTasks()
  startSSE()
  startPollingFallback()
})

onUnmounted(() => {
  stopSSE()
  stopPollingFallback()
})
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <h3 style="margin-top: 0">提交任务</h3>
      <el-input
        v-model="submitInput"
        type="textarea"
        :rows="3"
        placeholder="粘贴 115 分享链接，例如：https://115.com/s/abc123?password=xyz"
      />
      <div style="margin-top: 12px; text-align: right">
        <el-button type="primary" :loading="submitting" @click="submit">
          提交
        </el-button>
      </div>
    </el-card>

    <el-card>
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        "
      >
        <h3 style="margin: 0">任务列表</h3>
        <el-select
          v-model="filterStatus"
          multiple
          collapse-tags
          placeholder="筛选状态"
          style="width: 240px"
          @change="fetchTasks"
        >
          <el-option
            v-for="opt in statusOptions.filter((o) => o.value)"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
      <el-table
        :data="filteredTasks"
        v-loading="loading"
        style="width: 100%"
        empty-text="暂无任务"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column
          prop="share_url"
          label="分享链接"
          show-overflow-tooltip
        />
        <el-table-column
          prop="target_path"
          label="目标路径"
          show-overflow-tooltip
        />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="error_msg"
          label="错误信息"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed'"
              link
              size="small"
              @click="retry(row.id)"
            >
              重试
            </el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'done'"
              link
              size="small"
              @click="editCategory(row)"
            >
              修正分类
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
