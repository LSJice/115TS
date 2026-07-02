<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.name as string)

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

function go(name: string) {
  router.push({ name })
}
</script>

<template>
  <el-container class="app-container">
    <el-aside width="200px" class="app-aside">
      <div
        style="
          height: 60px;
          line-height: 60px;
          text-align: center;
          color: #fff;
          font-size: 18px;
          font-weight: bold;
        "
      >
        115 自动转存
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="transparent"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="go"
      >
        <el-menu-item index="tasks">
          <el-icon><Document /></el-icon>
          <span>任务</span>
        </el-menu-item>
        <el-menu-item index="history">
          <el-icon><Clock /></el-icon>
          <span>历史</span>
        </el-menu-item>
        <el-menu-item index="browser">
          <el-icon><FolderOpened /></el-icon>
          <span>网盘浏览</span>
        </el-menu-item>
        <el-menu-item index="config">
          <el-icon><Setting /></el-icon>
          <span>配置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div></div>
        <div>
          <el-tag v-if="auth.loggedIn" type="success" size="small">已登录</el-tag>
          <el-tag v-else type="warning" size="small">未登录</el-tag>
          <el-button
            type="text"
            style="margin-left: 16px; color: #f56c6c"
            @click="handleLogout"
          >
            退出
          </el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script lang="ts">
import { Document, Clock, FolderOpened, Setting } from '@element-plus/icons-vue'
export default { components: { Document, Clock, FolderOpened, Setting } }
</script>
