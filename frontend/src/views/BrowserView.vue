<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { dirsApi } from '@/api/dirs'
import type { DirRoot, DirNode } from '@/types'

const roots = ref<DirRoot[]>([])
const currentItems = ref<DirNode[]>([])
const breadcrumb = ref<{ name: string; cid: number }[]>([])
const loading = ref<boolean>(false)
const error = ref<string>('')

async function fetchRoots() {
  loading.value = true
  error.value = ''
  try {
    const resp = await dirsApi.roots()
    roots.value = resp.roots || []
    if (roots.value.length > 0) {
      await browse(roots.value[0].cid, roots.value[0].name)
    }
  } catch (e: any) {
    const status = e.response?.status
    if (status === 401) {
      error.value = '未登录 115，请先到登录页扫码'
    } else {
      error.value = `加载根目录失败：${e.message}`
    }
  } finally {
    loading.value = false
  }
}

async function browse(cid: number, name?: string) {
  loading.value = true
  error.value = ''
  try {
    const resp = await dirsApi.browse(cid)
    currentItems.value = resp.items || []
    // 更新面包屑
    if (name !== undefined) {
      // 从根重新进入时重置
      const existingIdx = breadcrumb.value.findIndex((b) => b.cid === cid)
      if (existingIdx >= 0) {
        breadcrumb.value = breadcrumb.value.slice(0, existingIdx + 1)
      } else {
        // 检查是否是 roots 中的根
        const root = roots.value.find((r) => r.cid === cid)
        if (root) {
          breadcrumb.value = [{ name: root.name, cid: root.cid }]
        } else {
          breadcrumb.value.push({ name, cid })
        }
      }
    }
  } catch (e: any) {
    error.value = `浏览失败：${e.message}`
    currentItems.value = []
  } finally {
    loading.value = false
  }
}

function enterNode(node: DirNode) {
  if (!node.is_dir) return
  browse(node.cid, node.name)
}

function jumpTo(index: number) {
  const target = breadcrumb.value[index]
  if (target) browse(target.cid)
}

onMounted(() => {
  fetchRoots()
})
</script>

<template>
  <el-card>
    <h3 style="margin-top: 0">网盘浏览</h3>

    <div style="margin-bottom: 12px">
      <el-tag
        v-for="r in roots"
        :key="r.cid"
        style="margin-right: 8px; cursor: pointer"
        :type="
          breadcrumb[0]?.cid === r.cid ? 'primary' : 'info'
        "
        @click="browse(r.cid, r.name)"
      >
        {{ r.name }}
      </el-tag>
    </div>

    <el-breadcrumb separator="/" style="margin-bottom: 12px">
      <el-breadcrumb-item
        v-for="(b, idx) in breadcrumb"
        :key="b.cid"
        @click="jumpTo(idx)"
      >
        <a href="javascript:void(0)">{{ b.name }}</a>
      </el-breadcrumb-item>
    </el-breadcrumb>

    <el-alert
      v-if="error"
      :title="error"
      type="warning"
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-table
      :data="currentItems"
      v-loading="loading"
      style="width: 100%"
      empty-text="目录为空或未登录"
      @row-dblclick="(row: DirNode) => enterNode(row)"
    >
      <el-table-column label="名称">
        <template #default="{ row }">
          <el-icon v-if="row.is_dir" color="#409eff"><Folder /></el-icon>
          <el-icon v-else color="#909399"><Document /></el-icon>
          <span
            style="margin-left: 8px; cursor: pointer"
            @click="enterNode(row)"
          >
            {{ row.name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          {{ row.is_dir ? '文件夹' : '文件' }}
        </template>
      </el-table-column>
      <el-table-column prop="cid" label="CID" width="120" />
    </el-table>
  </el-card>
</template>
