/* ============================================================================
 * Mock · 账号与会话域（login / getuserinfo / logout / generalnext / 用户增删改查 …）
 * ----------------------------------------------------------------------------
 * 角色裁剪的可验收性（裁定 B）：`login` 读取前端仅在 Mock 模式下附加的 `devRole`
 * （缺省 administrator），并把角色写进会话，使「按角色裁剪侧栏 / 路由」在 Mock 下可完整验收。
 * 口令校验宽松（任意非空口令通过；空口令 → C4），真实口令规则 md5(passwd + loginID) 由 store 负责。
 * ========================================================================== */
import { hoursBefore, pad, pick, ymdhms } from './data/util'

const VALID_ROLES = ['administrator', 'manager', 'operator', 'customer', 'visitor']

/** 角色 → 权限清单（镜像 §2.9.8 角色授权表；'*' 全量，'xxx*' 前缀通配） */
export const ROLE_PERMISSIONS = {
  administrator: ['*'],
  manager: ['*'],
  operator: [
    'topic*', 'asset*', 'render*', 'topicversion*',
    'layoutqry', 'platformqry', 'artifactqry', 'accountqry', 'publishrecordqry',
    'publishpush', 'publishcheck', 'generalnext', 'getuserinfo', 'logout',
    //★ 2026-09-23「第三方账号管理」：operator 可自管本人平台账号（归属由服务端强制）
    'accountadd', 'accountmodify', 'accountdel', 'accounthealth'
  ],
  customer: [
    'topicqry', 'assetqry', 'topicassetqry', 'renderjobqry', 'artifactqry',
    'layoutqry', 'platformqry', 'topicversionqry', 'getuserinfo', 'logout',
    //★ 2026-09-23「第三方账号管理」：customer 开放本人账号读/写/巡检（不含 visitor）
    'accountqry', 'accountadd', 'accountmodify', 'accountdel', 'accounthealth'
  ],
  visitor: ['platformqry', 'layoutqry', 'artifactqry', 'getuserinfo', 'logout']
}

/** 角色 → 开发态账号档案 */
const PROFILES = {
  administrator: { loginID: 'chenlh', realName: '陈立恒' },
  manager: { loginID: 'zhoumin', realName: '周敏' },
  operator: { loginID: 'lisiyuan', realName: '李思远' },
  customer: { loginID: 'wangys', realName: '王雨珊' },
  visitor: { loginID: 'zhaoym', realName: '赵一鸣' }
}

/** 会话表：sessionID → { role, loginID }；★ 刷新页面后按 sessionID 内的角色回退解析，避免被迫重登 */
const sessions = new Map()
const SESSION_RE = /^mock-(administrator|manager|operator|customer|visitor)-\d+$/

function resolveSession(sessionID) {
  const id = String(sessionID || '')
  if (!id) return null
  const hit = sessions.get(id)
  if (hit) return hit
  const matched = SESSION_RE.exec(id)
  if (!matched) return null
  const role = matched[1]
  return { role, loginID: PROFILES[role].loginID }
}

/** 用户台账（P-11 管理员） */
const USERS = VALID_ROLES.flatMap((role, roleIndex) =>
  Array.from({ length: roleIndex === 0 ? 3 : 2 }, (unused, i) => {
    const profile = i === 0 ? PROFILES[role] : { loginID: `${role.slice(0, 3)}${roleIndex}${i}`, realName: pick(['沈知微', '顾南屏', '陆文洲', '苏景和', '方叙白'], roleIndex * 2 + i) }
    return {
      recID: `US${pad(roleIndex * 4 + i + 1, 6)}`,
      loginID: profile.loginID,
      realName: profile.realName,
      roleName: role,
      department: pick(['内容运营部', '数字资产部', '平台技术部', '综合管理部'], roleIndex + i),
      status: '1',
      // 字段名对齐 ch_*.txt 权威列名（裁定 a1）：regYMDHMS = 创建时间
      regYMDHMS: ymdhms(hoursBefore(2400 - roleIndex * 100 - i * 20)),
      lastLoginYMDHMS: ymdhms(hoursBefore(6 + roleIndex * 3 + i))
    }
  })
)

const userDict = new Map()

function roleOf(body) {
  return resolveSession(body.sessionID)
}

/** 新建记录用的当前时间（14 位 YMDHMS） */
function nowStr() {
  const d = new Date()
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

export const handlers = {
  login: (body) => {
    const { loginID = '', passwd = '', devRole = '' } = body
    if (loginID === 'expired') return { __err: { code: 'B8', content: '会话已失效，请重新登录' } }
    if (loginID === 'error') return { __err: { code: 'C4', content: '账号或口令不正确' } }
    if (!loginID || !passwd) return { __err: { code: 'C4', content: '请输入账号与口令' } }
    const role = VALID_ROLES.includes(devRole) ? devRole : 'administrator'
    const profile = PROFILES[role]
    const sessionID = `mock-${role}-${Date.now()}`
    sessions.set(sessionID, { role, loginID })
    return {
      data: {
        sessionID,
        loginID,
        realName: profile.realName,
        roleName: role,
        mock: '1'
      }
    }
  },

  // 自助注册（本期不做页面，保留可联调路径）
  registration: (body) => {
    if (!body.loginID || !body.passwd) return { __err: { code: 'C4', content: '账号与口令均为必填项' } }
    if (USERS.some((item) => item.loginID === body.loginID)) {
      return { __err: { code: 'CA', content: `账号 ${body.loginID} 已存在` } }
    }
    return { data: { success: '1', loginID: body.loginID, note: 'Mock 环境仅登记，不写入真实用户库' } }
  },

  getuserinfo: (body) => {
    const session = roleOf(body)
    if (!session) return { __err: { code: 'B8', content: '会话已失效，请重新登录' } }
    const profile = PROFILES[session.role]
    return {
      data: {
        loginID: session.loginID || profile.loginID,
        realName: profile.realName,
        avatarUrl: '',
        roleName: session.role,
        roles: [session.role],
        permissions: ROLE_PERMISSIONS[session.role] || []
      }
    }
  },

  logout: (body) => {
    sessions.delete(String(body.sessionID || ''))
    return { data: { success: '1' } }
  },

  usersearch: (body, ctx) => {
    const keyword = String(body.keyword || '').trim()
    const roleFilter = String(body.roleName || '')
    const list = USERS.filter((item) => {
      const matchKeyword = !keyword || item.loginID.includes(keyword) || item.realName.includes(keyword)
      const matchRole = !roleFilter || item.roleName === roleFilter
      return matchKeyword && matchRole
    })
    return ctx.paginate(list, body, 'usersearch', keyword)
  },

  userinfoqry: (body) => {
    const hit = USERS.find((item) => item.loginID === body.loginID || item.recID === body.recID)
    if (!hit) return { __err: { code: 'CB', content: '未查询到该用户' } }
    return { data: hit }
  },

  useradd: (body) => {
    if (!body.loginID || !body.realName) return { __err: { code: 'C4', content: '账号与姓名均为必填' } }
    if (USERS.some((item) => item.loginID === body.loginID)) {
      return { __err: { code: 'CA', content: `账号 ${body.loginID} 已存在` } }
    }
    const record = {
      recID: `US${pad(USERS.length + 1, 6)}`,
      loginID: body.loginID,
      realName: body.realName,
      roleName: VALID_ROLES.includes(body.roleName) ? body.roleName : 'customer',
      department: body.department || '内容运营部',
      status: '1',
      regYMDHMS: nowStr(),
      lastLoginYMDHMS: ''
    }
    USERS.unshift(record)
    return { data: record }
  },

  usermodify: (body) => {
    const index = USERS.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '用户记录标识无效' } }
    USERS[index] = { ...USERS[index], ...body, recID: USERS[index].recID }
    return { data: USERS[index] }
  },

  userdel: (body) => {
    const index = USERS.findIndex((item) => item.recID === body.recID)
    if (index < 0) return { __err: { code: 'BI', content: '用户记录标识无效' } }
    const [removed] = USERS.splice(index, 1)
    return { data: { success: '1', recID: removed.recID } }
  },

  usersavedata: (body) => {
    userDict.set(String(body.dictKey || ''), body.dictValue ?? null)
    return { data: { success: '1' } }
  },

  usergetdata: (body) => ({ data: { dictKey: body.dictKey || '', dictValue: userDict.get(String(body.dictKey || '')) ?? null } }),

  chkuserexist: (body) => ({ data: { loginID: body.loginID || '', exist: USERS.some((item) => item.loginID === body.loginID) ? '1' : '0' } }),

  smsrequest: (body) => ({ data: { success: '1', expireSeconds: 300, email: body.email || '', ttl: 600, cooldown: 60 } }),
  // 带 email 时模拟「邮箱验证码登录」（docker/accountsvc A7A0）：校验通过即回 sessionID
  smsverify: (body) => {
    const code = String(body.code || body.smsCode || '')
    if (code !== '000000') return { __err: { code: 'BM', content: '验证码不正确（Mock 固定为 000000）' } }
    if (!body.email) return { data: { success: '1' } }
    const role = VALID_ROLES.includes(body.devRole) ? body.devRole : 'administrator'
    const sessionID = `mock-${role}-${Date.now()}`
    sessions.set(sessionID, { role, loginID: body.email })
    return { data: { sessionID, loginID: body.email, realName: PROFILES[role].realName, roleName: role, mock: '1' } }
  },
  resetpasswd: () => ({ data: { success: '1' } }),

  generalnext: (body, ctx) => ctx.nextBuffer(body),

  // 占位端点：后端未实现（§2.9.1）→ 固定 C2
  genusersessionid: () => ({ __err: { code: 'C2', content: '该端点后端尚未实现（占位）' } }),
  gethomepagedata: () => ({ __err: { code: 'C2', content: '该端点后端尚未实现（占位）' } })
}

/** 供其它 mock 复用：当前请求的会话（未登录返回 null） */
export function currentSession(body) {
  return roleOf(body)
}

export const mockUsers = USERS
export default handlers
