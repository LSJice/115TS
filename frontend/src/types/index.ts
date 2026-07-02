// 与后端 app/schemas.py 对齐的接口类型

export interface TaskOut {
  id: number
  source: string
  raw_input: string
  share_url: string
  share_code: string | null
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  category: string | null
  target_path: string | null
  error_msg: string | null
  retry_count: number
  created_at: number
  started_at: number | null
  finished_at: number | null
}

export interface TaskCreate {
  raw_input: string
}

export interface TaskCategoryUpdate {
  category: string
  target_path_override: string | null
}

export type HistoryOut = TaskOut

export interface QRStartResp {
  qrcode_url: string
  state: string
}

export interface QRStatusResp {
  state: string
  message: string
}

export interface AuthCheckResp {
  logged_in: boolean
}

export interface ConfigOut {
  tmdb_api_key: string
  tmdb_language: string
  feishu_app_id: string
  feishu_app_token: string
  feishu_table_id: string
  feishu_link_column: string
  feishu_code_column: string
  feishu_remark_column: string
  feishu_poll_interval_minutes: number
  telegram_allowed_chat_ids: number[]
  telegram_allowed_user_ids: number[]
}

export interface ConfigUpdate {
  tmdb_api_key?: string
  tmdb_language?: string
  feishu_app_id?: string
  feishu_app_secret?: string
  feishu_app_token?: string
  feishu_table_id?: string
  feishu_link_column?: string
  feishu_code_column?: string
  feishu_remark_column?: string
  feishu_poll_interval_minutes?: number
  telegram_allowed_chat_ids?: number[]
  telegram_allowed_user_ids?: number[]
}

export interface FeishuTestResp {
  ok: boolean
  message: string
}

export interface DirRoot {
  name: string
  cid: number
}

export interface DirNode {
  name: string
  cid: number
  is_dir: boolean
}

export interface TaskStreamEvent {
  task_id: number
  status: TaskOut['status']
  target_path?: string | null
  error?: string | null
}
