<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { historyApi } from '@/api/history'
import type { HistoryOut } from '@/types'

const items = ref<HistoryOut[]>([])
const loading = ref<boolean>(false)
const query = ref<string>('')
const category = ref<string>('')

async function fetchHistory() {
  loading.value = true
  try {
    items.value = await historyApi.list({
      q: query.value || undefined,
      category: category.value || undefined,
      limit: 100,
    })
  } catch (e: any) {
    ElMessage.error(`加载历史失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function deleteItem(id: number) {
  try {
    await ElMessageBox.confirm(
      `确定删除历史记录 #${id}？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' },
    )
    await historyApi.delete(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(`删除失败：${e.message}`)
  }
}

function statusTagType(s: HistoryOut['status']) {
  return {
    done: 'success',
    failed: 'danger',
    skipped: 'info',
    pending: 'info',
    running: 'warning',
  }[s]
}

function formatTime(ts: number | null): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchHistory()
})
</script>

<template>
  <el-card>
    <div
      style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      "
    >
      <h3 style="margin: 0">转存历史</h3>
      <div style="display: flex; gap: 8px">
        <el-input
          v-model="query"
          placeholder="搜索链接/路径"
          clearable
          style="width: 240px"
          @keyup.enter="fetchHistory"
          @clear="fetchHistory"
        />
        <el-input
          v-model="category"
          placeholder="分类"
          clearable
          style="width: 120px"
          @keyup.enter="fetchHistory"
          @clear="fetchHistory"
        />
        <el-button type="primary" @click="fetchHistory">搜索</el-button>
      </div>
    </div>
    <el-table
      :data="items"
      v-loading="loading"
      style="width: 100%"
      empty-text="暂无历史记录"
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
      <el-table-column label="完成时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.finished_at) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="error_msg"
        label="错误信息"
        show-overflow-tooltip
      />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            type="text"
            size="small"
            style="color: #f56c6c"
            @click="deleteItem(row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
