<template>
  <div class="flex min-h-screen items-center justify-center bg-ch-base p-2xl">
    <div
      class="grid w-full max-w-[960px] overflow-hidden rounded-2xl border border-ch-border bg-ch-surface shadow-modal lg:grid-cols-[1.05fr_1fr]"
    >
      <!-- 品牌区 -->
      <section class="hidden flex-col justify-between gap-3xl bg-ch-sidebar p-3xl lg:flex">
        <div class="flex items-center gap-sm">
          <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-ch-primary text-ch-text-inverse">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
              <rect x="0" y="0" width="6" height="6" rx="1.5" />
              <rect x="8" y="0" width="6" height="6" rx="1.5" />
              <rect x="0" y="8" width="6" height="6" rx="1.5" />
              <rect x="8" y="8" width="6" height="6" rx="1.5" />
            </svg>
          </span>
          <span class="text-[15px] font-semibold text-ch-text-primary">内容中枢</span>
        </div>

        <div class="flex flex-col gap-md">
          <h2 class="text-h2 text-ch-text-primary">内容生产与投递中台</h2>
          <ul class="flex flex-col gap-sm text-body-s text-ch-text-secondary">
            <li v-for="feature in FEATURES" :key="feature" class="flex items-center gap-sm">
              <i class="fa fa-angle-right text-caption text-ch-primary" aria-hidden="true"></i>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </div>

        <p class="text-caption text-ch-text-tertiary">内部系统 · 请使用分配给你的账号登录</p>
      </section>

      <!-- 表单区 -->
      <section class="p-3xl">
        <h1 class="text-h1 text-ch-text-primary">登录</h1>
        <p class="mt-xs text-body-s text-ch-text-secondary">
          {{ mode === 'email' ? '输入邮箱，获取 6 位验证码登录' : '请输入账号与口令' }}
        </p>

        <!-- 登录方式切换：邮箱验证码（Resend 发信）/ 账号口令；VITE_PASSWORD_LOGIN=false 时只保留邮箱 -->
        <div v-if="allowPassword" class="mt-xl flex gap-xs rounded-lg bg-ch-base p-[3px]" role="tablist">
          <button
            v-for="item in MODES"
            :key="item.value"
            type="button"
            role="tab"
            :aria-selected="mode === item.value"
            class="h-8 flex-1 rounded-md text-body-s transition-colors duration-150"
            :class="mode === item.value ? 'bg-ch-surface font-medium text-ch-text-primary shadow-sm' : 'text-ch-text-secondary'"
            @click="switchMode(item.value)"
          >
            {{ item.label }}
          </button>
        </div>

        <form class="mt-2xl flex flex-col gap-xl" novalidate @submit.prevent="handleSubmit">
          <template v-if="mode === 'email'">
            <div class="flex flex-col gap-xs">
              <label for="email" class="text-body-s text-ch-text-secondary">邮箱</label>
              <input
                id="email"
                v-model.trim="form.email"
                type="email"
                autocomplete="email"
                class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
                placeholder="name@example.com"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label for="code" class="text-body-s text-ch-text-secondary">验证码</label>
              <div class="flex gap-sm">
                <input
                  id="code"
                  v-model.trim="form.code"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  class="h-9 min-w-0 flex-1 rounded-md border border-ch-border bg-ch-input px-md font-mono text-body tracking-[0.3em] text-ch-text-primary placeholder:tracking-normal placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
                  placeholder="6 位数字"
                />
                <button
                  type="button"
                  class="h-9 shrink-0 rounded-lg border border-ch-border px-md text-body-s text-ch-text-primary transition-colors duration-150 hover:border-ch-primary disabled:cursor-not-allowed disabled:text-ch-text-disabled"
                  :disabled="sending || countdown > 0"
                  @click="handleSendCode"
                >
                  {{ sending ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : codeSent ? '重新发送' : '获取验证码' }}
                </button>
              </div>
              <p v-if="codeSent" class="text-caption text-ch-text-tertiary">
                验证码已发送至 {{ sentTo }}，{{ Math.round(codeTtl / 60) }} 分钟内有效；没收到请检查垃圾邮件。
              </p>
            </div>
          </template>

          <template v-else>
          <div class="flex flex-col gap-xs">
            <label for="loginID" class="text-body-s text-ch-text-secondary">账号</label>
            <input
              id="loginID"
              v-model.trim="form.loginID"
              type="text"
              autocomplete="username"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              placeholder="登录账号"
            />
          </div>

          <div class="flex flex-col gap-xs">
            <label for="passwd" class="text-body-s text-ch-text-secondary">口令</label>
            <input
              id="passwd"
              v-model="form.passwd"
              type="password"
              autocomplete="current-password"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary placeholder:text-ch-text-tertiary focus:border-ch-border-focus"
              placeholder="登录口令"
            />
          </div>
          </template>

          <!--
            开发态角色（裁定 B）：仅当 VITE_USE_MOCK === 'true' 时渲染，生产构建下不出现；
            且 devRole 字段仅在 Mock 模式下附加到登录请求（store 侧控制），真实模式不污染请求体。
          -->
          <div v-if="isMock" class="flex flex-col gap-xs">
            <label for="devRole" class="text-body-s text-ch-text-secondary">开发态角色</label>
            <select
              id="devRole"
              v-model="form.role"
              class="h-9 rounded-md border border-ch-border bg-ch-input px-md text-body text-ch-text-primary"
            >
              <option v-for="item in ROLE_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
            <p class="text-caption text-ch-text-tertiary">
              仅 Mock 模式可见：账号填 <code class="font-mono">expired</code> 验证会话失效（B8）路径，
              填 <code class="font-mono">error</code> 验证失败态不清空输入；邮箱验证码固定为 <code class="font-mono">000000</code>。
            </p>
          </div>

          <!-- 错误态不清空输入（计划 Step 2 第 8 点） -->
          <p v-if="errorMessage" role="alert" class="rounded-lg border border-ch-danger px-md py-sm text-body-s text-ch-danger">
            {{ errorMessage }}
          </p>

          <button
            type="submit"
            class="h-9 min-w-[112px] rounded-lg bg-ch-primary px-lg text-body font-medium text-ch-text-inverse transition-colors duration-150 ease-out hover:bg-ch-primary-hover active:bg-ch-primary-active disabled:cursor-not-allowed disabled:bg-ch-text-disabled"
            :disabled="loading"
          >
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue3-toastify'
import { emailCodeRequest } from '@/api/user'
import { ROLE_OPTIONS, roleLabel, useUserStore } from '@/store/modules/user'

const MODES = [
  { value: 'email', label: '邮箱验证码' },
  { value: 'password', label: '账号口令' }
]
/** 口令登录入口：构建时 VITE_PASSWORD_LOGIN=false 可隐藏（纯邮箱登录部署） */
const allowPassword = import.meta.env.VITE_PASSWORD_LOGIN !== 'false'
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** 账号服务（docker/accountsvc A6A0 / A7A0）错误码 → 行内提示 */
function emailErrorText(error) {
  const code = error?.errCode || error?.data?.errCode
  const reason = error?.reason || error?.data?.reason
  if (code === 'BA') return '邮箱格式不正确'
  if (code === 'BE') return '该邮箱未开通，请联系管理员'
  if (code === 'BM') return '验证码错误或已过期，请重新获取'
  if (code === 'BN' && reason === 'cooldown') return '发送太频繁，请稍后再试'
  if (code === 'BN' && reason === 'rate_limited') return '发送次数过多，请一小时后再试'
  if (code === 'BN') return '验证码邮件发送失败，请稍后重试'
  if (code === 'CI') return '账号服务不可用，请稍后重试'
  return error?.MSG?.content || error?.message || '登录失败，请稍后重试'
}

const FEATURES = ['主题与素材统一管理', '版式渲染与合规校验', '投递留痕与审计追溯']

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 开发态角色下拉仅在 Mock 模式下渲染（裁定 B）；生产构建（VITE_USE_MOCK=false）下不出现
const isMock = import.meta.env.VITE_USE_MOCK === 'true'

function readRoleFromQuery() {
  const value = typeof route.query.role === 'string' ? route.query.role : ''
  return ROLE_OPTIONS.some((item) => item.value === value) ? value : ROLE_OPTIONS[0].value
}

const mode = ref('email')
const form = reactive({ loginID: '', passwd: '', email: '', code: '', role: readRoleFromQuery() })
const loading = ref(false)
const errorMessage = ref('')

/* ---------- 邮箱验证码 ---------- */
const sending = ref(false)
const codeSent = ref(false)
const sentTo = ref('')
const codeTtl = ref(600)
const countdown = ref(0)
let timer = null

function switchMode(value) {
  mode.value = value
  errorMessage.value = ''
}

function startCountdown(seconds) {
  clearInterval(timer)
  countdown.value = seconds
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
}

onBeforeUnmount(() => clearInterval(timer))

async function handleSendCode() {
  errorMessage.value = ''
  if (!EMAIL_RE.test(form.email)) {
    errorMessage.value = '请输入正确的邮箱'
    return
  }
  sending.value = true
  try {
    const res = await emailCodeRequest({ email: form.email })
    const data = res?.data || res || {}
    codeSent.value = true
    sentTo.value = data.email || form.email
    codeTtl.value = Number(data.ttl) || 600
    startCountdown(Number(data.cooldown) || 60)
    document.getElementById('code')?.focus()
  } catch (error) {
    errorMessage.value = emailErrorText(error)
    const retryAfter = Number(error?.retryAfter || error?.data?.retryAfter)
    if (retryAfter > 0) startCountdown(retryAfter)
  } finally {
    sending.value = false
  }
}

/** ?redirect= 回跳（仅接受站内相对路径，避免开放重定向） */
const redirect = computed(() => {
  const value = route.query.redirect
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/'
  return value
})

function greeting() {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

function welcomeAndGo() {
  const who = userStore.realName || userStore.username
  const roles = userStore.roles.map(roleLabel).join('、')
  // 登录成功按当前时段 toast 欢迎
  toast.success(`${greeting()}，${who}（${roles}）`)
  return router.replace(redirect.value)
}

async function handleEmailSubmit() {
  if (!EMAIL_RE.test(form.email)) {
    errorMessage.value = '请输入正确的邮箱'
    return
  }
  if (!/^\d{6}$/.test(form.code)) {
    errorMessage.value = '请输入 6 位验证码'
    return
  }
  loading.value = true
  try {
    await userStore.loginByEmailCode({ email: form.email, code: form.code, role: form.role })
    await welcomeAndGo()
  } catch (error) {
    errorMessage.value = emailErrorText(error)
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  errorMessage.value = ''
  if (mode.value === 'email') return handleEmailSubmit()
  if (!form.loginID) {
    errorMessage.value = '请输入账号'
    return
  }
  if (!form.passwd) {
    errorMessage.value = '请输入口令'
    return
  }

  loading.value = true
  try {
    await userStore.login({ loginID: form.loginID, passwd: form.passwd, role: form.role })
    await welcomeAndGo()
  } catch (error) {
    // 失败时保留用户已填内容，只提示原因。
    // 非 B0 的 errCode 由 http.js 统一 toast `MSG.content`；此处做行内提示（同文案）。
    errorMessage.value = error?.MSG?.content || error?.message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>
