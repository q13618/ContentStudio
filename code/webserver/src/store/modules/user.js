/* ============================================================================
 * user store（setup store） · Step 3 接管真实取数
 * ----------------------------------------------------------------------------
 * 对外契约（自 Step 2 起冻结，签名与语义均未改动）：
 *   state  : accessToken / username / realName / avatar / roles / permissions / isInitFinished
 *   actions: login({ loginID, passwd, role? }) / getInfo() / logout()
 *            / waitInitFinished() / hasRole(roles) / hasPermission(cmd) / resetAccessToken()
 *
 * ★ Step 3 变更（裁定 A）：`fetchLogin` / `fetchUserInfo` 改为调用 `@/api/user` 的
 *   `login` / `getUserInfo`，并删除 Step 2 的 DEV_* 假数据；
 *   Login.vue / AppSidebar.vue / AppTopBar.vue 依赖的导出（ROLE_OPTIONS / roleLabel）保持不变。
 *
 * ★ 口令规则：`md5(passwd + loginID)`（由本 store 计算后传给后端，前端不存明文）。
 * ★ 开发态角色（裁定 B）：仅当 `VITE_USE_MOCK === 'true'` 时向登录请求附加 `devRole`，
 *   真实模式下**不发送**该字段，避免污染真实请求体。
 * ★ B8（会话失效）：由 `utils/http.js` 响应拦截统一清会话 + 跳登录；`getInfo` 失败时本 store
 *   亦按 Step 2 行为清会话（resetAccessToken），两者语义一致。
 * ★ 禁用 pinia persist 插件（基线 user.js:318-330 的 persist 因缺插件而失效，属缺陷，不继承）。
 * ★ 角色取值与 2.9.8 一致：administrator / manager / operator / customer / visitor。
 * ========================================================================== */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { md5 } from 'js-md5'
import { getAccessToken, setAccessToken, removeAccessToken } from '@/utils/accessToken'
import { login as loginApi, getUserInfo as getUserInfoApi, logout as logoutApi, emailCodeLogin as emailCodeLoginApi } from '@/api/user'
import { router, resetRouter } from '@/router'

/** 五个角色（后端 roleName 取值；顺序即登录页开发态下拉顺序） */
export const ROLE_OPTIONS = [
  { value: 'administrator', label: '管理员' },
  { value: 'manager', label: '业务主管' },
  { value: 'operator', label: '运营' },
  { value: 'customer', label: '客户（只读）' },
  { value: 'visitor', label: '访客' }
]

const VALID_ROLES = ROLE_OPTIONS.map((item) => item.value)
/** Mock 模式下 `devRole` 缺省值（裁定 B） */
const DEFAULT_DEV_ROLE = 'administrator'
/** 仅 Mock 模式才向登录请求附加 devRole（裁定 B：真实模式不发送，避免污染请求体） */
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/** 角色中文名（顶栏、登录欢迎语展示用） */
export function roleLabel(role) {
  const hit = ROLE_OPTIONS.find((item) => item.value === role)
  return hit ? hit.label : role
}

/**
 * 登录取数：POST `login`（business 报文由 http.js 放行返回，此处只取 `data`）。
 * 失败时由 http.js 已 toast `MSG.content`，错误继续向上抛给调用方（登录页保留表单内容）。
 *
 * ★ 出参信封（P-ENV-01，2026-09-21 远端实测）：`login` 属 account 域 **copy** 形态
 *   —— 顶层保留原业务字段 **且** 新增 `data` 副本，故读 `res.data.sessionID` 恒成立
 *   （账号服务回包本身已带 `data` 时跳过副本，不改原有语义）。
 * @param {{ loginID: string, passwd: string, devRole?: string }} payload
 * @returns {Promise<{ sessionID: string }>}
 */
async function fetchLogin(payload) {
  const res = await loginApi(payload)
  return res?.data || {}
}

/**
 * 用户信息取数：POST `getuserinfo`。
 * 角色取 `roles`（数组），兼容后端仅回 `roleName`（**真实后端即此形态**）。
 *
 * ★ 出参信封（P-ENV-01）：`getuserinfo` 属 account 域 **copy** 形态 → 业务字段在 `data` 内
 *   （远端实测 `data = {loginID,nickName,realName,email,sex,mobile,roleName,roleNameCN,
 *   activeFlag,extInService,authenticatedUser,avatarID}`）。
 * ★ 两处与后端实发不一致的字段（本步登记，不伪造数据源）：
 *   ① 头像：后端只回 `avatarID`（fileID），**未**回 `avatarUrl`；`fillFileUrls` 只把 `*FileID` 转 URL，
 *      命名不匹配 → 前端拿不到可用 URL，故 `avatarUrl` 保持空。顶栏头像用姓名首字展示，
 *      不受影响（见 AppTopBar 的 avatarText）；
 *   ② 权限清单：后端不下发 `permissions` → 恒为 `[]`。`hasPermission()` 因此对任何 CMD 均返回 false，
 *      但**当前无任何页面据它做鉴权门禁**（接口权限由后端 `ROLE_CMD_LIST` 强制），
 *      顶栏仅把它显示为「—」。
 * @returns {Promise<{ loginID: string, realName: string, avatarUrl: string, roles: string[], permissions: string[] }>}
 */
async function fetchUserInfo() {
  const res = await getUserInfoApi()
  const info = res?.data || {}
  const roles = Array.isArray(info.roles) && info.roles.length
    ? info.roles.filter((item) => VALID_ROLES.includes(item))
    : (VALID_ROLES.includes(info.roleName) ? [info.roleName] : [])
  return {
    loginID: info.loginID || '',
    realName: info.realName || '',
    avatarUrl: info.avatarUrl || '',
    roles,
    permissions: Array.isArray(info.permissions) ? info.permissions : []
  }
}

/** 角色/权限集合是否命中（支持精确、前缀通配 `xxx*`、全量 `*`） */
function matches(list, key) {
  return list.some((item) => item === '*' || item === key || (item.endsWith('*') && key.startsWith(item.slice(0, -1))))
}

export const useUserStore = defineStore('user', () => {
  /* ---------------- state（签名冻结） ---------------- */
  const accessToken = ref('')
  const username = ref('')
  const realName = ref('')
  const avatar = ref('')
  const roles = ref([])
  const permissions = ref([])
  const isInitFinished = ref(false)

  /* ---------------- 会话初始化 ---------------- */
  let resolveReady = null
  const readyPromise = new Promise((resolve) => {
    resolveReady = resolve
  })

  function markReady() {
    if (isInitFinished.value) return
    isInitFinished.value = true
    if (resolveReady) resolveReady()
  }

  /** 守卫第一步：等待会话初始化完成（本步为同步恢复 token，故立即就绪） */
  function waitInitFinished() {
    return isInitFinished.value ? Promise.resolve() : readyPromise
  }

  function resetSession() {
    accessToken.value = ''
    username.value = ''
    realName.value = ''
    avatar.value = ''
    roles.value = []
    permissions.value = []
  }

  function resetAccessToken() {
    removeAccessToken()
    resetSession()
  }

  /* ---------------- actions（签名冻结） ---------------- */

  /**
   * 登录：口令 md5(passwd + loginID) → fetchLogin → setAccessToken → getInfo。
   * `role` 仅在 Mock 模式下作为 `devRole` 附加（裁定 B），真实模式不发送该字段。
   */
  async function login({ loginID = '', passwd = '', role = '' } = {}) {
    const digest = md5(`${passwd}${loginID}`)
    const payload = { loginID, passwd: digest }
    if (USE_MOCK) payload.devRole = VALID_ROLES.includes(role) ? role : DEFAULT_DEV_ROLE
    const data = await fetchLogin(payload)
    if (!data || !data.sessionID) throw new Error('登录失败：未取得会话标识')
    accessToken.value = data.sessionID
    setAccessToken(data.sessionID)
    await getInfo()
    return data
  }

  /**
   * 邮箱验证码登录：校验成功后账号服务直接回 sessionID（与口令登录同形），之后流程与 login 一致。
   * `role` 同 login，仅 Mock 模式附加 devRole。
   */
  async function loginByEmailCode({ email = '', code = '', role = '' } = {}) {
    const payload = { email, code }
    if (USE_MOCK) payload.devRole = VALID_ROLES.includes(role) ? role : DEFAULT_DEV_ROLE
    const res = await emailCodeLoginApi(payload)
    const data = res?.data || {}
    if (!data.sessionID) throw new Error('登录失败：未取得会话标识')
    accessToken.value = data.sessionID
    setAccessToken(data.sessionID)
    await getInfo()
    return data
  }

  /**
   * 拉取当前用户信息。失败即按 B8 口径清会话（Step 3 由 http.js 拦截器统一处理 B8）并抛错，
   * 由调用方（路由守卫 / 登录页）决定后续跳转。
   */
  async function getInfo() {
    try {
      const info = await fetchUserInfo()
      username.value = info.loginID || ''
      realName.value = info.realName || ''
      avatar.value = info.avatarUrl || ''
      roles.value = Array.isArray(info.roles) ? info.roles : []
      permissions.value = Array.isArray(info.permissions) ? info.permissions : []
      return info
    } catch (error) {
      resetAccessToken()
      throw error
    }
  }

  /** 登出：调用 `logout` 通知后端 → 清会话 → 重置动态路由 → 回登录页 */
  async function logout() {
    // 即使后端登出失败（如会话已失效的 B8），也必须完成本地清会话，故显式捕获并记录，不吞异常来源
    try {
      await logoutApi({})
    } catch (error) {
      console.error('[user] 登出接口返回异常，已继续清理本地会话：', error)
    }
    resetAccessToken()
    resetRouter()
    if (router.currentRoute.value.path !== '/login') {
      await router.replace({ path: '/login' })
    }
  }

  /** 是否具备任一角色（传字符串或数组） */
  function hasRole(role) {
    const wanted = Array.isArray(role) ? role : [role]
    return wanted.some((item) => item === '*' || roles.value.includes(item))
  }

  /** 是否具备某端点权限（传字符串或数组） */
  function hasPermission(cmd) {
    const wanted = Array.isArray(cmd) ? cmd : [cmd]
    return wanted.some((item) => matches(permissions.value, item))
  }

  /* ---------------- 启动即恢复会话 ---------------- */
  accessToken.value = getAccessToken() || ''
  markReady()

  return {
    accessToken,
    username,
    realName,
    avatar,
    roles,
    permissions,
    isInitFinished,
    waitInitFinished,
    login,
    loginByEmailCode,
    getInfo,
    logout,
    hasRole,
    hasPermission,
    resetAccessToken
  }
})

export default useUserStore
