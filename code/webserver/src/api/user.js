/* ============================================================================
 * api 域：账号 / 会话（后端 subfunc/accountApi.py 的 CMD_MAP，§2.9.1）
 * ----------------------------------------------------------------------------
 * 统一范式（Step 3 要点 2）：一域一文件、只做「CMD → 请求」的映射，**不含业务逻辑**；
 * 返回值即 http.js 放行的**业务报文**（含 data / total / errCode），调用方自行解构。
 *
 * 覆盖 2.9.1 的 19 个 CMD 中的 18 个（`accounthealth` 归 `account.js`，与 P-11 同页使用）。
 * ========================================================================== */
import { createService } from '@/utils/http'

const svc = createService()

/** 登录（口令 md5(passwd + loginID) 由 store 计算后传入；Mock 额外读 devRole） */
export const login = (params) => svc.post('/login', params)
/** 自助注册（本期不做页面，保留映射） */
export const registration = (params) => svc.post('/registration', params)
/** 登出 */
export const logout = (params) => svc.post('/logout', params)
/** 当前用户信息（含 roleName / roles / permissions），路由守卫与顶栏使用 */
export const getUserInfo = (params) => svc.post('/getuserinfo', params)
/** 用户检索（P-11 管理员） */
export const userSearch = (params) => svc.post('/usersearch', params)
/** 用户详情（P-11） */
export const userInfoQry = (params) => svc.post('/userinfoqry', params)
/** 用户自定义数据存储 / 读取（页面偏好，可选） */
export const userSaveData = (params) => svc.post('/usersavedata', params)
export const userGetData = (params) => svc.post('/usergetdata', params)
/** 用户是否存在（注册校验，可选） */
export const chkUserExist = (params) => svc.post('/chkuserexist', params)
/** 短信与重置密码（可选） */
export const smsRequest = (params) => svc.post('/smsrequest', params)
export const smsVerify = (params) => svc.post('/smsverify', params)
export const resetPasswd = (params) => svc.post('/resetpasswd', params)
/**
 * 邮箱验证码登录（Resend 发信，docker/accountsvc 的 A6A0 / A7A0；复用 smsrequest / smsverify 通道）。
 * silent：错误由登录页按 errCode 行内提示，不再弹全局 toast。
 */
export const emailCodeRequest = (params) => svc.post('/smsrequest', params, { silent: true })
export const emailCodeLogin = (params) => svc.post('/smsverify', params, { silent: true })
/** 用户增 / 改 / 删（仅 administrator · manager，§2.9.8） */
export const userAdd = (params) => svc.post('/useradd', params)
export const userModify = (params) => svc.post('/usermodify', params)
export const userDel = (params) => svc.post('/userdel', params)
/** 取下一批缓冲数据（续取分页，配合 indexKey；免登录端点） */
export const generalNext = (params) => svc.post('/generalnext', params)
/** 占位端点：后端未实现，固定返回 C2（§2.9.1） */
export const genUserSessionId = (params) => svc.post('/genusersessionid', params)
export const getHomePageData = (params) => svc.post('/gethomepagedata', params)
