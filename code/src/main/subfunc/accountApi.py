#! /usr/bin/env python3
#encoding: utf-8

#Filename: accountApi.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub 账号 / 用户 / 会话业务域接入端点(见 plan/chAPIPost分拆方案.md 3.1 / 4.2 / 4.3)。
#
#本文件承载:
#  1) calUserCMDMapKeyList —— 权限/会话校验中枢(方案 4.3 裁定放本文件, 由 chAPIPost.post() 调用);
#      ★ 已修复基线缺陷: 基线 `CMDList += settings.NO_SESSIONID_CMD_LIST` 会就地修改默认参数
#        (模块级列表), 导致免登录命令跨请求累积进候选集合。本实现一律「先拷贝入参再合并」。
#  2) 18 个账号域 CMD 处理器(15 + 管理员专用 useradd/usermodify/userdel) + accounthealth;
#  3) 落库队列(CH_MYSQL)的**生产端**: registration / login / usermodify 三类报文投递给
#     processor/transferCHMysql.py(消费端)同步写入 USER_BASIC(生产/消费对照见「私有辅助」段首注释)。
#
#移植口径(已与需求方拍板: 「尽量移植博物馆实现」, 缺口处降级/占位):
#  可迁移(走账号服务, 与基线等价):
#      registration / login (A0A0) · logout (A5A0) · smsrequest (A6A0) · smsverify (A7A0)
#      resetpasswd (A9A0) · usersavedata (G1A0) · usergetdata (G2A0)
#  降级改写(museum 落本地用户表 comMysql.queryUserBasic, contentHub 无该表):
#      chkuserexist -> Redis 存在性 + 账号服务(AIA0) 双源判定
#      getuserinfo  -> 账号服务(A3A0) + Redis 用户档案
#      usersearch / userinfoqry -> Redis 用户档案(scanUserAllInfo/getUserAllInfo) + 查询缓冲
#  必须占位(museum 无实现, 无基线行为可搬):
#      genusersessionid / gethomepagedata -> C2(未实现), 待产品约定后落地
#  ★ 2026-09-20 补齐(原移植遗漏): useradd / usermodify / userdel —— museum 有实现(funcUserAdd L869 /
#      funcUserModify L1055 / funcUserDelete L976), contentHub 首轮未带; 三者**仅管理员**(settings.USER_ADMIN_ROLE_LIST),
#      且 useradd **不复用 registration**(自助注册全角色开放, 用户增删改仅管理员)
#  基线无对应(账号平台凭据健康):
#      accounthealth -> 汇总 ch_account 的 healthStatus
#      ★ SP4b(P3-6): 同一处理函数内承接**凭据健康巡检** —— action ∈ {check, refresh, probe} 时先触发
#        schedule/credentialCheck.runOnce(只读探活 + 回写 healthStatus/lastCheckYMDHMS + R-03 分级告警),
#        再重新汇总; **不新增 CMD**(端点总数仍 69), 且巡检**不做任何投递/发布**。

_VERSION="20260918"


import os
import sys

parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

import traceback

from config import basicSettings as settings

from common import globalDefinition as comGD

from common import funcCommon as comFC

from common import miscCommon as misc

from common import redisCommon as comDB

from common import mysqlCommon as comMysql

from common import queryBufferCommon as comQB

from subfunc import context as ctx

from subfunc import apiCommon

from subfunc import accountSvcClient


_processorPID = ctx._processorPID
_LOG = ctx._LOG
_DEBUG = ctx._DEBUG

#登录/注册报文落库队列(与基线 saveSet 队列语义一致: 由 mysql-writer 进程消费;
#contentHub 的消费者在后续子计划落地, 在此之前写入仅作为审计留痕, 不影响主流程)
MSG_QUEUE_KEY_CH_MYSQL = comGD._DEF_CH_MSG_QUEUE_MYSQL_TITLE

#用户检索的返回字段白名单(降级实现: 用户档案来自 Redis/账号服务)
USER_SEARCH_FIELD_LIST = ["loginID", "nickName", "realName", "roleName", "mobile", "email"]

#用户检索时允许 searchOption 过滤/排序的字段
USER_SEARCH_ALLOW_LIST = ["loginID", "nickName", "realName", "roleName", "mobile", "email"]


#===== 权限/会话校验中枢 begin =====

def calUserCMDMapKeyList(dataSet, CMDList = None):
    """向账号服务发 GAA0 取 sessionIDSet, 与 settings.ROLE_CMD_LIST 求交集得到本次请求可用的命令集合。

       出参: (userCMDMapKeyList, sessionIDSet, errCode)
         errCode == "B0" 表示权限校验通过; "B8" 表示无权限/会话无效; 其余为账号服务错误码。

       ★ 缺陷修复(方案 8.1 要求): 基线实现为
             CMDList += settings.NO_SESSIONID_CMD_LIST
         即向「默认参数引用的模块级列表」就地追加, 免登录命令会跨请求累积并污染注册表候选集合。
         本实现先拷贝入参, 再合并, 全程不修改任何入参或模块级对象。
    """
    sessionIDSet = {}
    errCode = "B0"

    sessionID = dataSet.get("sessionID", "")

    errCode, sessionIDSet = accountSvcClient.getSessionAndCmdList(sessionID)

    #先拷贝入参(修复基线就地追加缺陷), 再并入免登录命令集合
    userCMDMapKeyList = list(CMDList) if CMDList else []
    userCMDMapKeyList += list(settings.NO_SESSIONID_CMD_LIST)

    if sessionIDSet:
        roleName = sessionIDSet.get("roleName", "")
        sessionIDSet["sessionID"] = sessionID
        allowList = settings.ROLE_CMD_LIST.get(roleName, [])
        userCMDMapKeyList = list(set(allowList).intersection(set(userCMDMapKeyList)))

    #判断权限
    userCMD = dataSet.get("CMD")
    if userCMD not in userCMDMapKeyList:
        errCode = "B8"

    return userCMDMapKeyList, sessionIDSet, errCode

#===== 权限/会话校验中枢 end =====


#===== 私有辅助 begin =====

#落库队列(CH_MYSQL)的生产 / 消费对照 —— 契约以**消费端为准**(processor/transferCHMysql.py::funcProcTransferData):
#   registration      <- funcUserRegistration(本文件)     消费者: getUserInfo(A3A0) -> writeUser2UserBasic(USER_BASIC)
#   login             <- funcUserLogin(本文件)             同上
#   usermodify        <- funcUserModify(★管理员) / funcUserSaveData / funcResetPasswd   消费者: 重取 A3A0 并更新 USER_BASIC
#   useradd           <- funcUserAdd(本文件, ★仅管理员)   消费者: 取 A3A0 -> writeUser2UserBasic(与 registration 同一路)
#   userdel           <- funcUserDel(本文件, ★仅管理员)   消费者: 取 A3A0 -> queryUserBasic -> deleteUserBasic
#   putdatabufferlist —— contentHub 的查询缓冲为**进程内同步写**(common/queryBufferCommon.putQuery2Buffer),
#                        不做队列异步转存, 故无生产者
#★ 新增/调整生产侧时, 以上清单与消费端分派表必须同步(避免再次出现「消费端有分支、生产端无投递」)。

def _saveMsg2Queue(CMD, dataSet, rtnData, loginID):
    """把报文投递到落库队列 CH_MYSQL(消费者: processor/transferCHMysql.py)。

    队列契约(以消费端为准):
      CMD     —— 消费端分派的命令名(消费端统一 lower() 处理, 大小写不敏感);
      data    —— 原始请求报文(消费端读 data.loginID / data.sessionID);
      rtnData —— 账号服务回包(消费端读 rtnData.errCode / rtnData.loginID);
      loginID —— 操作者 loginID(会话上下文)。

    ★ 说明: data 原样投递(registration / login 的 data.loginID 是注册/登录的目标用户, 不可用会话
      操作者覆盖); 需要补齐 loginID / sessionID 的入口(usermodify)由调用方先经 _genUserSyncData 组包。
    """
    try:
        saveSet = {}
        saveSet["data"] = dataSet
        saveSet["rtnData"] = rtnData
        saveSet["CMD"] = CMD
        saveSet["loginID"] = loginID

        rtn = comDB.putMsg2Queue(MSG_QUEUE_KEY_CH_MYSQL, saveSet)

        if _DEBUG and _LOG:
            _LOG.info(f"D: DEBUG,rtn:{rtn},saveSet:{saveSet}")
    except Exception as e:
        if _LOG:
            _LOG.error(f"PID:{_processorPID},CMD:{CMD}, _saveMsg2Queue errMsg:{str(e)}")


def _genUserSyncData(dataSet, loginID, sessionID = ""):
    """生成「用户资料变更(usermodify)」落库报文的 data 段(不改动调用方原字典)。

    消费端 funcUserModify 需要 data.loginID(用户主键) 与 data.sessionID(再取 A3A0 用),
    而 usersavedata / resetpasswd 等入口的原始请求体可能只在会话上下文里带这两个字段, 故在此补齐。
    """
    saveData = dict(dataSet) if isinstance(dataSet, dict) else {}
    if not saveData.get("loginID"):
        saveData["loginID"] = loginID
    if not saveData.get("sessionID"):
        saveData["sessionID"] = sessionID
    return saveData


def _genSyncRtnData(result, errCode):
    """生成落库报文的 rtnData 段: 以账号服务回包为基底, 显式补齐已归一的 errCode。

    消费端各分支均以 rtnData.errCode == "B0" 判成败; 而账号服务对部分 CMD 把错误码放在
    MSG.errCode(见 subfunc/accountSvcClient.py::svcErrCode), 接入层已归一为 errCode ——
    此处按归一结果补齐, 保证生产端与消费端对「成败」的判定完全一致(不改动原 result 字典)。
    """
    syncRtn = dict(result) if isinstance(result, dict) else {}
    syncRtn["errCode"] = errCode
    return syncRtn


def _chkUserExistAnySource(loginID):
    """用户存在性双源判定: Redis 用户档案优先, 回落账号服务(AIA0)。
       说明: museum 用本地用户表判定, contentHub 无该表, 故降级为双源(任一命中即视为存在)。
       Redis 不可用时不影响账号服务判定(各自独立 try)。"""
    if not loginID:
        return False

    try:
        if comDB.chkUserExist(loginID):
            return True
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, redis chkUserExist failed, loginID:{loginID}, errMsg:{str(e)}")

    try:
        return accountSvcClient.chkUserExist(loginID)
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, account chkUserExist failed, loginID:{loginID}, errMsg:{str(e)}")

    return False


def _chkUserAdminArgs(sessionIDSet, dataSet, requireFieldList):
    """用户管理端点(useradd / usermodify / userdel)的公共前置校验:
       出参 (errCode, rtnField, loginID), errCode == "B0" 表示通过。

       管理员判定统一复用公共件 comFC.chkIsManager(roleName) —— **administrator 或 manager** 视为管理员,
       本文件不再自建角色清单;
       第一道请求级判定仍由 calUserCMDMapKeyList 按 settings.ROLE_CMD_LIST 完成(这三个 CMD 仅授权给
       settings.USER_ADMIN_ROLE_LIST 中的角色, 与 chkIsManager 的口径保持一致);
       非管理员 -> BG(权限不足); 必填缺失 -> C4(rtnField 指出缺哪个字段, 供报文的 %s 填充)。
    """
    loginID = dataSet.get("loginID") or dataSet.get("userID") or ""
    if not comFC.chkIsManager(sessionIDSet.get("roleName", "")):
        return "BG", "BG", loginID
    for fieldName in requireFieldList:
        if fieldName == "loginID":
            #loginID 允许经 userID 别名传入, 故按已归一的 loginID 判定
            if not loginID:
                return "C4", "loginID", loginID
        elif not dataSet.get(fieldName):
            return "C4", fieldName, loginID
    return "B0", "", loginID


def _getUserProfileFromRedis(loginID):
    """从 Redis 用户档案取信息(字段缺失时返回空字典), 与账号服务结果做补充。"""
    result = {}
    if not loginID:
        return result

    try:
        dataSet = comDB.getUserAllInfo(loginID)
        if isinstance(dataSet, dict):
            result = dataSet
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, redis getUserAllInfo failed, loginID:{loginID}, errMsg:{str(e)}")

    return result


def _packUserInfo(loginID, sessionID = ""):
    """组装用户信息(降级实现): 账号服务(A3A0) 与 Redis 用户档案合并, 账号服务优先。"""
    result = _getUserProfileFromRedis(loginID)

    svcInfo = accountSvcClient.getUserInfo(loginID, sessionID)
    if svcInfo:
        result.update(svcInfo)

    result["loginID"] = result.get("loginID", loginID)
    result["roleName"] = accountSvcClient.normalizeRoleName(result.get("roleName", ""))

    return result


def _genUserDataList(loginID, keyword = "", limitNum = 0):
    """生成用户检索结果列表(降级实现): Redis 用户清单 -> 逐条组装 -> 关键词过滤。
       说明: museum 走本地用户表 + SQL LIKE; contentHub 无该表, 退化为 Redis SCAN + 内存过滤,
             用户量级增长后需改为账号服务侧检索接口(登记为 SP2 待办)。"""
    dataList = []

    if loginID:
        dataList.append(_packUserInfo(loginID))
        return dataList

    maxNum = comGD._DEF_MAX_QUERY_LIMIT_NUM
    if limitNum and int(limitNum) > 0:
        maxNum = int(limitNum)

    try:
        userIDList = comDB.getAllUserIDList(maxNum = maxNum, key = f"*{keyword}*" if keyword else "*")
    except Exception as e:
        if _LOG:
            _LOG.warning(f"W: PID:{_processorPID}, redis getAllUserIDList failed, errMsg:{str(e)}")
        userIDList = []

    for userID in userIDList:
        userInfo = _packUserInfo(userID)
        if keyword:
            matched = False
            for fieldName in USER_SEARCH_FIELD_LIST:
                if keyword in str(userInfo.get(fieldName, "")):
                    matched = True
                    break
            if not matched:
                continue
        dataList.append(userInfo)

    return dataList


def _chkIsAuthenticatedUser(orgID):
    """是否认证用户(搬移自基线: extOrgID > 0 视为已认证)"""
    result = comGD._CONST_NO
    try:
        if int(orgID) > 0:
            result = comGD._CONST_YES
    except Exception:
        result = comGD._CONST_NO

    return result


def _chkIsInService(inService, activeFlag):
    """是否在服务中(搬移自基线: activeFlag == Y 且 inService != N)"""
    result = comGD._CONST_NO
    try:
        if activeFlag == comGD._CONST_YES and inService != comGD._CONST_NO:
            result = comGD._CONST_YES
    except Exception:
        result = comGD._CONST_NO

    return result

#===== 私有辅助 end =====


#===== 账号域 CMD 处理器 begin =====

#用户是否存在
def funcChkUserExist(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        loginID = dataSet.get("loginID")
        if not loginID:
            loginID = sessionIDSet.get("loginID", "")

        if loginID:
            if _chkUserExistAnySource(loginID):
                result["exist"] = comGD._CONST_YES
            else:
                result["exist"] = comGD._CONST_NO
        else:
            errCode = "B1"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户注册
def funcUserRegistration(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        errCode, rtnData = accountSvcClient.userLoginOrRegistration(dataSet)
        if isinstance(rtnData, dict):
            result = rtnData

        _saveMsg2Queue(CMD, dataSet, _genSyncRtnData(result, errCode), sessionIDSet.get("loginID", ""))

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户登录
def funcUserLogin(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        loginID = dataSet.get("loginID")
        if loginID:
            #检查用户是否存在, 如果不存在,就报错(基线用 accChkUserExist -> AIA0)
            if not accountSvcClient.chkUserExist(loginID):
                errCode = "B1"
        else:
            errCode = "B7"

        if errCode == "B0":
            errCode, rtnData = accountSvcClient.userLoginOrRegistration(dataSet)
            if isinstance(rtnData, dict):
                result = rtnData

            _saveMsg2Queue(CMD, dataSet, _genSyncRtnData(result, errCode), sessionIDSet.get("loginID", ""))

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户增加(★ 管理员专用, 与 registration 独立: 自助注册对所有角色开放, 本端点仅管理员可调)
def funcUserAdd(CMD, dataSet, sessionIDSet):
    result = {}
    try:
        lang = apiCommon.genLang(dataSet)
        errCode, rtnField, loginID = _chkUserAdminArgs(sessionIDSet, dataSet, ["loginID", "passwd"])
        if errCode == "B0":
            requestData = dict(dataSet)
            requestData["loginID"] = loginID
            #角色由管理员指定; 缺失/非法一律回落默认角色(不接受客户端任意取值)
            if requestData.get("roleName") not in settings.ROLE_CMD_LIST:
                requestData["roleName"] = settings.accountServiceDefaultRoleName
            errCode, rtnData = accountSvcClient.userLoginOrRegistration(requestData)   #A0A0: 账号服务侧建号
            if isinstance(rtnData, dict):
                result = {"loginID": rtnData.get("loginID", loginID),
                          "roleName": rtnData.get("roleName", requestData["roleName"])}
            #落库队列: useradd -> 消费端 funcUserRegistration(取 A3A0 -> writeUser2UserBasic);
            #★ 第 4 参为**操作者**(管理员)loginID, 消费端据此写 USER_BASIC.regID
            _saveMsg2Queue("useradd", _genUserSyncData(dataSet, loginID, sessionIDSet.get("sessionID", "")),
                           _genSyncRtnData(result, errCode), sessionIDSet.get("loginID", ""))
        result = apiCommon.genRtnResult(CMD, errCode, rtnField or errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户修改(★ 管理员专用): 角色变更走账号服务 AEA0; 资料由落库队列重取 A3A0 回写 USER_BASIC
def funcUserModify(CMD, dataSet, sessionIDSet):
    result = {}
    try:
        lang = apiCommon.genLang(dataSet)
        errCode, rtnField, loginID = _chkUserAdminArgs(sessionIDSet, dataSet, ["loginID", "roleName"])
        if errCode == "B0" and dataSet.get("roleName") not in settings.ROLE_CMD_LIST:
            errCode, rtnField = "C7", "roleName"
        if errCode == "B0":
            #本系统角色 -> 账号服务角色由 accountSvcClient.accountServiceForward 映射(settings.ROLE_ACCOUNT_ROLE)
            errCode, rtnData = accountSvcClient.accountServiceForward(
                accountSvcClient.ACCOUNT_CMD_MODIFY_ROLE, dataSet, roleName = dataSet.get("roleName"))
            if errCode == "B0":
                result = {"loginID": loginID, "roleName": dataSet.get("roleName")}
            #落库队列: usermodify -> 消费端 funcUserModify(取 A3A0 -> writeUser2UserBasic)
            _saveMsg2Queue("usermodify", _genUserSyncData(dataSet, loginID, sessionIDSet.get("sessionID", "")),
                           _genSyncRtnData(result, errCode), sessionIDSet.get("loginID", ""))
        result = apiCommon.genRtnResult(CMD, errCode, rtnField or errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户删除(★ 管理员专用)
#★ contentHub 的账号服务未提供「删除用户」CMD(仅 A0A0/A2A0/A3A0/A5A0/A6A0/A7A0/A9A0/AIA0/AEA0/G1A0/G2A0/GAA0),
#  故本端点只删本地 USER_BASIC(经落库队列异步执行), 账号服务侧显式标注 accountSvcDelete="0"(不静默假装成功);
#  另加防自删: 不允许通过本端点删除当前登录账号。
def funcUserDel(CMD, dataSet, sessionIDSet):
    result = {}
    try:
        lang = apiCommon.genLang(dataSet)
        errCode, rtnField, loginID = _chkUserAdminArgs(sessionIDSet, dataSet, ["loginID"])
        operatorLoginID = sessionIDSet.get("loginID", "")
        if errCode == "B0" and loginID == operatorLoginID:
            errCode, rtnField = "C7", "loginID"
        if errCode == "B0":
            result = {"loginID": loginID, "localDelete": "queued", "accountSvcDelete": "0"}
            #落库队列: userdel -> 消费端 funcUserDel(取 A3A0 -> queryUserBasic -> deleteUserBasic)
            _saveMsg2Queue("userdel", _genUserSyncData(dataSet, loginID, sessionIDSet.get("sessionID", "")),
                           _genSyncRtnData(result, errCode), operatorLoginID)
        result = apiCommon.genRtnResult(CMD, errCode, rtnField or errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户登出
def funcUserLogout(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        #角色转换: 基线仅取 dataSet["roleName"], 而该字段实际由 post() 放在 sessionIDSet 中,
        #故此处补一层回落(否则基线该路径恒判 B8)。转换表见 settings.ROLE_ACCOUNT_ROLE。
        userRoleName = dataSet.get("roleName", "")
        if not userRoleName:
            userRoleName = sessionIDSet.get("roleName", "")

        errCode, rtnData = accountSvcClient.userLogout(dataSet, roleName = userRoleName)
        if isinstance(rtnData, dict):
            result = rtnData

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户查询(检索)
def funcUserSearch(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        loginID = dataSet.get("loginID", "")
        keyword = dataSet.get("keyword", "")
        searchOption = dataSet.get("searchOption")
        limitNum = dataSet.get("limitNum", 0)

        sessionID = sessionIDSet.get("sessionID", "")
        indexKeyDataSet = apiCommon.genIndexKeyDataSet(dataSet, ["loginID", "keyword", "searchOption", "mode"])
        indexKey = comQB.genBufferIndexKey(CMD, sessionID, indexKeyDataSet)

        beginNum, endNum = apiCommon.getQueryBeginEndNum(dataSet)
        forceFlashFlag = dataSet.get("forceFlashFlag", comGD._CONST_NO)

        if comQB.chkNeedFlashQuery(indexKey, forceFlashFlag):
            dataList = _genUserDataList(loginID, keyword = keyword, limitNum = limitNum)

            if searchOption:
                searchRtnSet = comFC.handleSearchOption(searchOption, USER_SEARCH_ALLOW_LIST, dataList)
                if searchRtnSet.get("rtn") == "B0":
                    dataList = searchRtnSet.get("data", [])

            #临时缓存机制(与基线一致): 查询结果先入 Redis 缓冲, 再按分页取回
            indexKey = comQB.putQuery2Buffer(indexKey, dataList)

        result = comQB.getQueryBufferComplte(indexKey, beginNum = beginNum, endNum = endNum)
        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户信息查询
def funcUserInfoQuery(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        loginID = dataSet.get("loginID", "")
        if not loginID:
            loginID = sessionIDSet.get("loginID", "")

        if loginID:
            userInfo = _packUserInfo(loginID, sessionIDSet.get("sessionID", ""))
            roleName = userInfo.get("roleName", "")

            result["loginID"] = userInfo.get("loginID", loginID)
            result["roleName"] = roleName
            result["roleNameCN"] = settings.ROLE_EN_CN_NAME_DATA.get(roleName, "")
            result["nickName"] = userInfo.get("nickName", "")
            result["realName"] = userInfo.get("realName", "")
            result["mobile"] = userInfo.get("mobile", "")
            result["email"] = userInfo.get("email", "")
            result["activeFlag"] = userInfo.get("activeFlag", comGD._CONST_YES)
        else:
            errCode = "B1"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户信息获取
def funcGetUserInfo(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        loginID = dataSet.get("loginID", "")
        if not loginID:
            loginID = sessionIDSet.get("loginID", "")

        if loginID:
            userInfo = _packUserInfo(loginID, sessionIDSet.get("sessionID", ""))

            result["loginID"] = userInfo.get("loginID", loginID)
            result["nickName"] = userInfo.get("nickName", "")
            result["realName"] = userInfo.get("realName", "")
            result["email"] = userInfo.get("email", "")
            result["sex"] = userInfo.get("sex", "")
            result["mobile"] = userInfo.get("mobile", "")
            result["roleName"] = userInfo.get("roleName", "")
            result["roleNameCN"] = settings.ROLE_EN_CN_NAME_DATA.get(result["roleName"], "")
            result["activeFlag"] = userInfo.get("activeFlag", comGD._CONST_YES)
            result["extInService"] = _chkIsInService(userInfo.get("extInService", ""),
                                                     userInfo.get("activeFlag", comGD._CONST_YES))
            result["authenticatedUser"] = _chkIsAuthenticatedUser(userInfo.get("extOrgID", 0))

            #头像: 库内只存 fileID, 出参转 URL(文件访问只经 fileStorageCommon, 故延迟导入避免厂商 SDK 传递依赖)
            avatarID = userInfo.get("avatarID", "")
            if avatarID:
                try:
                    from common import fileStorageCommon as comFS
                    result["avatarID"] = comFS.getTempLocation(avatarID, privateFlag = True)
                except Exception as e:
                    if _LOG:
                        _LOG.warning(f"W: PID:{_processorPID}, avatarID url convert failed, errMsg:{str(e)}")
                    result["avatarID"] = ""
            else:
                result["avatarID"] = ""
        else:
            errCode = "B1"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#短信验证请求
def funcSMSRequest(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        errCode, rtnData = accountSvcClient.smsRequest(dataSet)
        if isinstance(rtnData, dict):
            result = rtnData

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#短信验证反馈
def funcSMSVerify(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        errCode, rtnData = accountSvcClient.smsVerify(dataSet)
        if isinstance(rtnData, dict):
            result = rtnData

        #验证码登录成功(账号服务回 sessionID, 如 docker/accountsvc 的邮箱验证码登录): 与 login 同路落库 USER_BASIC
        if errCode == "B0" and result.get("sessionID") and result.get("loginID"):
            _saveMsg2Queue("login", {"loginID": result.get("loginID")},
                           _genSyncRtnData(result, errCode), result.get("loginID"))

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#用户重置口令
def funcResetPasswd(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        errCode, rtnData = accountSvcClient.resetPasswd(dataSet)
        if isinstance(rtnData, dict):
            result = rtnData

        #口令变更后同步 USER_BASIC(投递 usermodify, 消费端重取 A3A0 -> writeUser2UserBasic)
        if errCode == "B0":
            syncData = _genUserSyncData(dataSet, sessionIDSet.get("loginID", ""),
                                        sessionIDSet.get("sessionID", ""))
            _saveMsg2Queue("usermodify", syncData, _genSyncRtnData(result, errCode),
                           sessionIDSet.get("loginID", ""))

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#保存用户数据
def funcUserSaveData(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        if sessionIDSet.get("loginID"):
            errCode, rtnData = accountSvcClient.saveUserData(dataSet)
            if isinstance(rtnData, dict):
                result = rtnData

            #用户资料变更后同步 USER_BASIC(投递 usermodify, 消费端重取 A3A0 -> writeUser2UserBasic)
            if errCode == "B0":
                syncData = _genUserSyncData(dataSet, sessionIDSet.get("loginID", ""),
                                            sessionIDSet.get("sessionID", ""))
                _saveMsg2Queue("usermodify", syncData, _genSyncRtnData(result, errCode),
                               sessionIDSet.get("loginID", ""))
        else:
            errCode = "BA"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#获取用户存储数据
def funcUserGetData(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        if sessionIDSet.get("loginID"):
            errCode, rtnData = accountSvcClient.getUserData(dataSet)
            if isinstance(rtnData, dict):
                result = rtnData
        else:
            errCode = "BA"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#获取下一批数据(查询缓冲续取)
def funcGeneralNext(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)

        tempUserID = sessionIDSet.get("loginID", "")

        indexKey = dataSet.get("indexKey", "")
        beginNum, endNum = apiCommon.getQueryBeginEndNum(dataSet)

        if indexKey and tempUserID:
            if comQB.chkBufferExist(indexKey):
                rtnData = comQB.getQueryBufferComplte(indexKey, beginNum = beginNum, endNum = endNum)
                rtnData["dataLen"] = str(len(rtnData.get("data", [])))
                result = rtnData
            else:
                errCode = "CC"

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result


#生成用户会话(museum 无实现, 占位)
def funcGenUserSessionID(CMD, dataSet, sessionIDSet):
    return apiCommon.genNotImplementedResult(CMD, dataSet, sessionIDSet)


#获取首页数据(museum 无实现, 占位)
def funcGetHomePageData(CMD, dataSet, sessionIDSet):
    return apiCommon.genNotImplementedResult(CMD, dataSet, sessionIDSet)


#账号(平台凭据)健康汇总(★ SP4b · P3-6: 同一处理函数内承接凭据巡检, **不新增 CMD**)
def funcAccountHealth(CMD, dataSet, sessionIDSet):
    result = {}
    errCode = "B0"

    try:
        lang = apiCommon.genLang(dataSet)
        action = str(dataSet.get("action", "")).strip().lower()

        #★ SP4b: action ∈ {check, refresh, probe} 时先触发一次凭据健康巡检
        #  (复用 schedule/credentialCheck.py: 只读探活 + 回写 healthStatus/lastCheckYMDHMS + R-03 分级告警),
        #  再重新汇总。巡检**不做任何投递/发布**; 不新增 CMD(端点总数仍 69)。
        #★ 2026-09-23 手改(第三方账号管理/巡检归属收窄, 方案甲): 非管理员按登录 loginID 收窄
        #  (巡检明细与 healthSummary 同口径, 否则非管理员点一次巡检就能改写全表账号);
        #  管理员(administrator/manager)保持全量; 定时任务不经本入口 -> 全量行为不变。
        #  见 plan/前端开发计划.md「第三方账号管理」。
        scopeOwner = "" if comFC.chkIsManager(sessionIDSet.get("roleName", "")) else sessionIDSet.get("loginID", "")

        checkResult = None
        if action in ("check", "refresh", "probe"):
            try:
                #函数内延迟导入: 接入层与调度层在导入期解耦(调度层不 import main/subfunc)
                from schedule import credentialCheck
                checkResult = credentialCheck.runOnce({
                    "accountID": dataSet.get("accountID", 0),
                    "platform": dataSet.get("platform", ""),
                    "ownerID": scopeOwner,
                })
            except Exception as e:
                checkResult = {"errMsg": f"凭据巡检执行失败: {str(e)}"}

        tableName = comMysql.tablename_convertor_ch_account()
        #★ 2026-09-23 手改(第三方账号管理/巡检归属收窄): 汇总必须与巡证明细同口径, 否则非管理员
        #  仍可从 healthSummary 读到全站账号总数与健康分布(信息泄露); 关键字传参 ownerID。
        dataList = comMysql.query_ch_account(tableName, ownerID = scopeOwner)

        summary = {"total": len(dataList), "OK": 0, "EXPIRING": 0, "INVALID": 0, "UNKNOWN": 0}
        for data in dataList:
            healthStatus = data.get("healthStatus") or "UNKNOWN"
            if healthStatus in summary:
                summary[healthStatus] += 1
            else:
                summary["UNKNOWN"] += 1

        result["healthSummary"] = summary

        if checkResult is not None:
            #真巡检(action 非空): checkedAt = 本次巡检时间(checkResult 自带)
            result["credentialCheck"] = checkResult
            result["checkedAt"] = checkResult.get("checkedAt", "")
        else:
            #★ 2026-09-23 手改(巡检改为手工触发/工作台快照口径): 工作台首屏**不传 action**(只汇总、不巡检),
            #  故汇总需自带「快照时点」——取本次范围内各账号 lastCheckYMDHMS 的**最大值**(即最近一次真实
            #  巡检时间; 14 位 YYYYMMDDHHMMSS 可直接字典序比较); 从未巡检/无记录 -> 空串(前端显示 —)。
            #  ★ 该时点同样受归属收窄(dataList 已按 ownerID 过滤), 不会泄露他人账号的巡检时间。
            lastCheckList = []
            for data in dataList:
                if isinstance(data, dict):
                    stamp = str(data.get("lastCheckYMDHMS") or "").strip()
                    if stamp:
                        lastCheckList.append(stamp)
            result["checkedAt"] = max(lastCheckList) if lastCheckList else ""

        result = apiCommon.genRtnResult(CMD, errCode, errCode, lang, rtnData = result)

    except Exception as e:
        result = apiCommon.genErrResult(CMD, e)

    return result

#===== 账号域 CMD 处理器 end =====


CMD_MAP = {
    "chkuserexist": funcChkUserExist,
    "registration": funcUserRegistration,
    "login": funcUserLogin,
    #★ 管理员专用三端点(2026-09-20 补齐 museum 账号域): useradd 与 registration **独立**, 不可互相替代
    "useradd": funcUserAdd,
    "usermodify": funcUserModify,
    "userdel": funcUserDel,
    "logout": funcUserLogout,
    "usersearch": funcUserSearch,
    "userinfoqry": funcUserInfoQuery,
    "getuserinfo": funcGetUserInfo,
    "smsrequest": funcSMSRequest,
    "smsverify": funcSMSVerify,
    "resetpasswd": funcResetPasswd,
    "usersavedata": funcUserSaveData,
    "usergetdata": funcUserGetData,
    "generalnext": funcGeneralNext,
    "genusersessionid": funcGenUserSessionID,
    "gethomepagedata": funcGetHomePageData,
    "accounthealth": funcAccountHealth,
}

#占位端点清单(供诊断/落地跟踪使用, 不参与注册表合并)
PLACEHOLDER_CMD_LIST = ["genusersessionid", "gethomepagedata"]


if __name__ == "__main__":
    pass
    print("accountApi CMD_MAP keys:", list(CMD_MAP.keys()))
    print("placeholder:", PLACEHOLDER_CMD_LIST)
