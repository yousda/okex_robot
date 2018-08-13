#!/usr/bin/python
# -*- coding: utf-8 -*-
# encoding: utf-8
#客户端调用，用于查看API返回结果

import os,sys
from sys import version_info  

if version_info.major < 3:
    magetoolpth = '/usr/local/lib/python2.7/site-packages'
    if magetoolpth not in sys.path:
        sys.path.append(magetoolpth)
    else:
        print('heave magetool pth')

import socket
import threading
import time
import json

from magetool import pathtool
from magetool import timetool
sys.path.append('util')
import signTool

import orderObj

def sayMsg(msg):
    cmd = 'say %s'%(msg)
    os.system(cmd)
    print msg


class TradeTool(object):
    """docstring for ClassName"""
    def __init__(self,configdic,tradeconfiddic,isTest = True):
        #期货交易工具
        self.configdic = configdic
        self.isTest = isTest

    # "iOkexRate":0.0005,     //okex主动成交费率
    # "pOkexRate":0.0002,     //okex被动成交费率
    # "iBiemexRate":0.00075,  //bitmex主动成交费率
    # "pBiemexRate":-0.00025,   //bitmex被动成交费率
    # "stepPercent":0.005,    //下单网格价格百分比大小
    # "movePercent":0.003,    //网格滑动价格百分比
    # "normTime":3,           //基准价格重新计算时间,单位:小时
    # "reconfigTime":60       //配置文件检测刷新时间，单位:秒
        self.tradeConfig = None
        self.iOkexRate = 0.0005
        self.pOkexRate = 0.0002
        self.iBiemexRate = 0.00075
        self.pBiemexRate = -0.00025
        self.stepPercent = 0.005
        self.movePercent = 0.003
        self.normTime = 3*60*60    #小时换算成秒

        self.initTraddeConfig(tradeconfiddic)

        #okex
        self.okexSeckey = configdic['okex']['secretkey']
        self.okexDataSocket = None
        self.okexDatathr = None
        self.okexTradeSocket = None
        self.okexTradethr = None



        #bitmex
        self.bitmexSeckey = configdic['bitmex']['secretkey']
        self.bitmexDataSocket = None
        self.bitmexDatathr = None
        self.bitmexTradeSocket = None
        self.bitmexTradethr = None


        self.avrOkexBuy = 0.0
        self.avrBitmexBuy = 0.0

        self.avrOkexSell = 0.0
        self.avrBitmexSell = 0.0

        self.avrDelayTime = 1*60*60   #单位:秒

        self.okexBTC = 0.0
        self.bitmexBTC = 0.0

        self.tradeSavePth = 'log/trade.txt'
        
        self.socketstate = {'bd':False,'bt':False,'od':False,'ot':False}

        ptime = int(time.time())
        self.lastimedic = {'bd':ptime,'bt':ptime,'od':ptime,'ot':ptime}


        self.isShowLog = True

        self.okexDatas = []             #买一价，卖一价，接收数据时间
        self.bitmexDatas = []           #买一价，卖一价, 接收数据时间
        self.lastSub = {}               #okex的卖一价和bitmex的买一价的差价，bitmex的卖一价和okex的买一价的差价,时间差,最后接收时间
        self.obsubs = []
        self.bosubs = []
        self.arvsub = 0                 #滑动差值
        self.okexTradeMsgs = []         #bitmex已下单，等待bitmex成交后，再吃单成交的okex

        self.openTrade = []             #保存的开仓对

        self.bCIDBase = 0               #bitmex的用户自定义定单ID基数
        self.oCIDBase = 0               #okex用户自定义定单ID基数

        self.bCIDData = {}
        #定单ID生成算法：b_orderType_CIDBase_time
        self.oCIDData = {}

        self.initSocket()

    def setLogShow(self,isShowLog):
        self.isShowLog = isShowLog

    def initSocket(self):
        self.initOkexTradeSocket()
        self.initOkexDataSocket()
        self.initBitmexTradeSocket()
        self.initBitmexDataSocket()
    
    def initOkexTradeSocket(self):
        isErro = False
        try:
            print('connecting okex http trade server:',self.configdic['okex']['httpaddr'],self.configdic['okex']['httpport'])
            self.okexTradeSocket = socket.socket()  # instantiate
            self.okexTradeSocket.connect((self.configdic['okex']['httpaddr'], self.configdic['okex']['httpport']))  # connect to the server
            print('okex http trade server connected!')
            def okexTradeRun():
                while True:
                    data = self.okexTradeSocket.recv(100*1024)
                    isOK = False
                    try:
                        datadic = json.loads(data.decode())
                        isOK = True
                    except Exception as e:
                        print(data)
                    if isOK:
                        self.onOkexTradeBack(datadic)
            self.okexTradethr = threading.Thread(target=okexTradeRun,args=())
            self.okexTradethr.setDaemon(True)
            self.okexTradethr.start()
            self.socketstate['ot'] = True
        except Exception as e:
            print('connect okex http trade server erro...')
            self.okexTradeSocket = None
            isErro =  True
        return (not isErro)
    def initOkexDataSocket(self):
        isErro = False
        try:
            print('connecting okex ws data server:',self.configdic['okex']['wsaddr'],self.configdic['okex']['wsport'])
            self.okexDataSocket = socket.socket()  # instantiate
            self.okexDataSocket.connect((self.configdic['okex']['wsaddr'], self.configdic['okex']['wsport']))  # connect to the server
            print('okex ws data server connected!')
            def okexDataRun():
                while True:
                    data = self.okexDataSocket.recv(100*1024)
                    datadic = json.loads(data.decode())
                    self.onOkexData(datadic)

            self.okexDatathr = threading.Thread(target=okexDataRun,args=())
            self.okexDatathr.setDaemon(True)
            self.okexDatathr.start()
            self.socketstate['od'] = True
        except Exception as e:
            print('connect erro okex ws data...')
            self.okexDataSocket = None
            isErro =  True
        return (not isErro)
    
    def initBitmexDataSocket(self):
        isErro = False
        try:
            print('connecting bitmex ws data server:',self.configdic['bitmex']['wsaddr'],self.configdic['bitmex']['wsport'])
            self.bitmexDataSocket = socket.socket()  # instantiate
            self.bitmexDataSocket.connect((self.configdic['bitmex']['wsaddr'], self.configdic['bitmex']['wsport']))  # connect to the server
            print('bitmex ws data server connected!')
            def bitmexDataRun():
                while True:
                    data = self.bitmexDataSocket.recv(100*1024)
                    isOKBitmexData = False
                    try:
                        datadic = json.loads(data.decode())
                        isOKBitmexData = True
                    except Exception as e:
                        print(data)
                    if isOKBitmexData:
                        self.onBitmexData(datadic)
                    
            self.bitmexDatathr = threading.Thread(target=bitmexDataRun,args=())
            self.bitmexDatathr.setDaemon(True)
            self.bitmexDatathr.start()
            self.socketstate['bd'] = True
        except Exception as e:
            print('connect erro bitmex ws data...')
            self.bitmexDataSocket = None
            isErro =  True
        return (not isErro)
    def initBitmexTradeSocket(self):
        isErro = False
        try:
            print('connecting bitmex Trade data server:',self.configdic['bitmex']['httpaddr'],self.configdic['bitmex']['httpport'])
            self.bitmexTradeSocket = socket.socket()  # instantiate
            self.bitmexTradeSocket.connect((self.configdic['bitmex']['httpaddr'], self.configdic['bitmex']['httpport']))  # connect to the server
            print('bitmex ws Trade server connected!')
            def okexDataRun():
                while True:
                    data = self.bitmexTradeSocket.recv(100*1024)
                    isOKBitmexTrade = False
                    try:
                        datadic = json.loads(data.decode())
                        isOKBitmexTrade = True
                    except Exception as e:
                        print(data)
                    if isOKBitmexTrade:
                        self.onBitmexTradeBack(datadic)
            self.bitmexTradethr = threading.Thread(target=okexDataRun,args=())
            self.bitmexTradethr.setDaemon(True)
            self.bitmexTradethr.start()
            self.socketstate['bt'] = True
        except Exception as e:
            print('connect erro bitmex trade...')
            self.bitmexTradeSocket = None
            isErro =  True
        return (not isErro)


    def timeconvent(self,utcstrtime):
        timest = timetool.utcStrTimeToTime(utcstrtime)
        timeint = int(timest)
        ltimeStr = str(timetool.timestamp2datetime(timeint,True))   
        return timeint,ltimeStr 

    def updateDataSub(self):
        #self.okexDatas = []             #买一价，卖一价，接收数据时间
        #self.bitmexDatas = []           #买一价，卖一价, 接收数据时间
        #self.lastSub = []               #okex的卖一价和bitmex的买一价的差价，bitmex的卖一价和okex的买一价的差价,时间差,最后接收时间
        if self.okexDatas and self.bitmexDatas:
            self.lastSub['ob'] = {'subOB':self.okexDatas[1][0] - self.bitmexDatas[0][0],'odeep':self.okexDatas[1][1],'bdeep':self.bitmexDatas[0][1]}
            self.lastSub['bo'] = {'subBO':self.bitmexDatas[1][0] - self.okexDatas[0][0],'odeep':self.okexDatas[0][1],'bdeep':self.bitmexDatas[1][1]}
            self.lastSub['otime'] = self.okexDatas[2]
            self.lastSub['btime'] = self.bitmexDatas[2]
            self.lastSub['subtime'] = self.okexDatas[2] - self.bitmexDatas[2]
            # print('-'*20)
            if self.isShowLog:
                print('ob:',round(self.lastSub['ob']['subOB'],3),self.lastSub['ob']['odeep'],self.lastSub['ob']['bdeep'],'bo:',round(self.lastSub['bo']['subBO'],3),self.lastSub['bo']['odeep'],self.lastSub['bo']['bdeep'],self.lastSub['subtime'])
            self.tradeTest()
    #初始化交易参数,如单次下单合约值，谁主动成交，谁被动成交,交易手续费等
    def initTraddeConfig(self,conf):
        self.tradeConfig = conf
        self.iOkexRate = self.tradeConfig['iOkexRate']
        self.pOkexRate = self.tradeConfig['pOkexRate']
        self.iBiemexRate = self.tradeConfig['iBiemexRate']
        self.pBiemexRate = self.tradeConfig['pBiemexRate']
        # self.stepPercent = self.tradeConfig['stepPercent']
        self.stepPercent = (self.iOkexRate + self.iBiemexRate)*conf['stepPercent']
        # self.movePercent = self.tradeConfig['movePercent']
        self.movePercent = self.stepPercent*conf['movePercent']
        self.normTime = self.tradeConfig['normTime']*60*60    #小时换算成秒
        self.baseAmount = self.tradeConfig['baseAmount']      #okex合约张数，bitmex要X100

    #生成用户自定义定单ID
    def crecteOrderCID(self,market,orderType):
        # self.bCIDBase = 0               #bitmex的用户自定义定单ID基数
        # self.oCIDBase = 0               #okex用户自定义定单ID基数
        if market == 'bitmex':
            self.bCIDBase += 1
            cid = 'b-'+ orderType + '-' + str(self.bCIDBase) + '-' + str(int(time.time()))
            return cid
        elif market == 'okex':#实际上okex的api接口并不支持设置用户定义ID
            self.oCIDBase += 1
            cid = 'o-'+ orderType + '-' + str(self.oCIDBase) + '-' + str(int(time.time()))
            return cid
        return ''

    def openOB(self,subpurce,isReset = False): #开仓,okex买入，bitmex卖出
        cid = self.crecteOrderCID('bitmex','os')
        msg = {'type':'os','amount':self.baseAmount*100,'price':self.bitmexDatas[1][0],'islimit':1,'cid':cid}
        self.bCIDData[cid] = {'msg':msg,'state':0}
        if self.sendMsgToBitmexTrade('os', msg):
            self.okexTradeMsgs.append({'type':'ol','amount':self.baseAmount,'cid':cid})
            if isReset:
                self.obsubs.pop()
                self.obsubs.append(self.bitmexDatas[1][0]-self.okexDatas[1][0])
            else:
                self.obsubs.append(self.bitmexDatas[1][0]-self.okexDatas[1][0])
            print(self.obsubs)
            return msg
        return None
        
        
    def closeOB(self,subpurce,closeAll = False,isReset = False):#平仓,okex卖出，bitmex买入
        if closeAll:
            pp = len(self.obsubs)
            cid = self.crecteOrderCID('bitmex','cs')
            msg = {'type':'cs','amount':self.baseAmount*100*pp,'price':self.bitmexDatas[0][0],'islimit':1,'cid':cid}
            self.bCIDData[cid] = {'msg':msg,'state':0}
            if self.sendMsgToBitmexTrade('cs', msg):
                self.okexTradeMsgs.append({'type':'cl','amount':self.baseAmount*pp,'cid':cid})
                self.obsubs = []
                return msg
        else:
            cid = self.crecteOrderCID('bitmex','cs')
            msg = {'type':'cs','amount':self.baseAmount*100,'price':self.bitmexDatas[0][0],'islimit':1,'cid':cid}
            self.bCIDData[cid] = {'msg':msg,'state':0}
            if self.sendMsgToBitmexTrade('cs', msg):
                self.okexTradeMsgs.append({'type':'cl','amount':self.baseAmount,'cid':cid})
                if not isReset:
                    subprice = self.obsubs.pop()
                return msg
            print(self.obsubs)
        return None
        

    def openBO(self,subpurce,isReset = False): #开仓,bitmex买入,okex卖出
        cid = self.crecteOrderCID('bitmex','ol')
        msg = {'type':'ol','amount':self.baseAmount*100,'price':self.bitmexDatas[0][0],'islimit':1,'cid':cid}
        self.bCIDData[cid] = {'msg':msg,'state':0}
        if self.sendMsgToBitmexTrade('ol', msg):
            self.okexTradeMsgs.append({'type':'os','amount':self.baseAmount,'cid':cid})
            if isReset:
                self.bosubs.pop()
                self.bosubs.append(self.bitmexDatas[0][1]-self.okexDatas[0][0])
            else:
                self.bosubs.append(self.bitmexDatas[0][1]-self.okexDatas[0][0])
            print(self.bosubs)
            return msg
        return None

    def closeBO(self,subpurce,closeAll = False,isReset = False):#平仓,bitmex卖出,okex买入
        if closeAll:
            pp =len(self.bosubs)
            cid = self.crecteOrderCID('bitmex','cl')
            msg = {'type':'cl','amount':self.baseAmount*100*pp,'price':self.bitmexDatas[0][0],'islimit':1,'cid':cid}
            self.bCIDData[cid] = {'msg':msg,'state':0}
            if self.sendMsgToBitmexTrade('cl', msg):
                self.okexTradeMsgs.append({'type':'cs','amount':self.baseAmount*pp,'cid':cid})
                self.bosubs = []
                return msg
        else:
            cid = self.crecteOrderCID('bitmex','cl')
            msg = {'type':'cl','amount':self.baseAmount*100,'price':self.bitmexDatas[0][0],'islimit':1,'cid':cid}
            self.bCIDData[cid] = {'msg':msg,'state':0}
            if self.sendMsgToBitmexTrade('cl', msg):
                self.okexTradeMsgs.append({'type':'cs','amount':self.baseAmount,'cid':cid})
                if not isReset:
                    subprice = self.bosubs.pip()
                print(self.bosubs)
                return msg
        return None
    #检测是否需要下单
    def tradeTest(self):
        
        lastOBsub = self.lastSub['ob']['subOB']
        lastBOsub = self.lastSub['bo']['subBO']
        if lastOBsub <= 0:  #bitmex价格高于okex
            maxprice = self.bitmexDatas[1][0]
            stepprice = maxprice * self.stepPercent
            if self.isShowLog:
                print('stepprice=%.2f'%(stepprice))
            if len(self.obsubs) < 1:
                if abs(lastOBsub) > stepprice and len(self.obsubs) < 1:
                    self.openOB(stepprice)
                elif abs(lastOBsub) > stepprice*((1+self.stepPercent)^2) and len(self.obsubs) < 2:
                    self.openOB(stepprice*((1+self.stepPercent)^2))
                elif abs(lastOBsub) > stepprice*((1+self.stepPercent)^3) and len(self.obsubs) < 3:
                    self.openOB(stepprice*((1+self.stepPercent)^3))
                elif abs(lastOBsub) > stepprice*((1+self.stepPercent)^4) and len(self.obsubs) < 4:
                    self.openOB(stepprice*((1+self.stepPercent)^4))
                elif abs(lastOBsub) > stepprice*((1+self.stepPercent)^5) and len(self.obsubs) < 5:
                    self.openOB(stepprice*((1+self.stepPercent)^5))
                elif abs(lastOBsub) > stepprice*((1+self.stepPercent)^6) and len(self.obsubs) < 6:
                    self.openOB(stepprice*((1+self.stepPercent)^6))
            elif abs(lastOBsub) > stepprice and len(self.bosubs) > 0:
                self.closeBO(stepprice,closeAll = True)
        elif lastBOsub < 0:
            maxprice = self.okexDatas[1][0]
            stepprice = maxprice * self.stepPercent
            if self.isShowLog:
                print('stepprice=%.2f'%(stepprice))
            if len(self.obsubs) < 1:
                if abs(lastBOsub) > stepprice and len(self.obsubs) < 1:
                    self.openBO(stepprice)
                elif abs(lastBOsub) > stepprice*((1+self.stepPercent)^2) and len(self.obsubs) < 2:
                    self.openBO(stepprice*((1+self.stepPercent)^2))
                elif abs(lastBOsub) > stepprice*((1+self.stepPercent)^3) and len(self.obsubs) < 3:
                    self.openBO(stepprice*((1+self.stepPercent)^3))
                elif abs(lastBOsub) > stepprice*((1+self.stepPercent)^4) and len(self.obsubs) < 4:
                    self.openBO(stepprice*((1+self.stepPercent)^4))
                elif abs(lastBOsub) > stepprice*((1+self.stepPercent)^5) and len(self.obsubs) < 5:
                    self.openBO(stepprice*((1+self.stepPercent)^5))
                elif abs(lastBOsub) > stepprice*((1+self.stepPercent)^6) and len(self.obsubs) < 6:
                    self.openBO(stepprice*((1+self.stepPercent)^6))
            elif abs(lastBOsub) > stepprice and len(self.bosubs) > 0:
                self.closeOB(stepprice,closeAll = True)

        # "iOkexRate":0.0005,     //okex主动成交费率
        # "pOkexRate":0.0002,     //okex被动成交费率
        # "iBiemexRate":0.00075,  //bitmex主动成交费率
        # "pBiemexRate":-0.00025,   //bitmex被动成交费率
        # "stepPercent":0.005,    //下单网格价格百分比大小
        # "movePercent":0.003,    //网格滑动价格百分比
        # "normTime":3,           //基准价格重新计算时间,单位:小时
        # "reconfigTime":60       //配置文件检测刷新时间，单位:秒
    


    # 下单数据格式:
    # 开多,
    # {type:ol,amount:100,price:100,islimit:1}
    # 平多,
    # {type:cl,amount:100,price:100,islimit:1}
    # 开空,
    # {type:os,amount:100,price:100,islimit:1}
    # 平空
    # {type:cs,amount:100,price:100,islimit:1}

    # 获取定单状态
    # 获取所有定单状态
    # {type:getall}
    def getAllTrade(self,market = 'all'):
        msg = {'type':'getall'}
        if market == 'all':
            self.sendMsgToOkexTrade('getall', msg)
            self.sendMsgToBitmexTrade('getall', msg)
        elif market == 'okex':
            self.sendMsgToOkexTrade('getall', msg)
        elif market == 'bitmex':
            self.sendMsgToBitmexTrade('getall', msg)
    # 使用定单ID获取定单状态
    # {type:getID,id:123456}
    def getTrade(self,market,orderID):
        msg = {'type':'getID','id':orderID}
        if market == 'okex':
            self.sendMsgToOkexTrade('getID', msg)
        elif market == 'bitmex':
            self.sendMsgToBitmexTrade('getID', msg)
    # 取消某个定单
    # {type:cancel,id:123456}
    def cancelOneTrade(self,market,orderID):
        msg = {'type':'cancel','id':orderID}
        if market == 'okex':
            self.sendMsgToOkexTrade('cancel', msg)
        elif market == 'bitmex':
            self.sendMsgToBitmexTrade('cancel', msg)
    # 取消所有定单
    # {type:cancelall}
    def cancelAllTrade(self,market):
        msg = {'type':'cancelall'}
        if market == 'all':
            self.sendMsgToOkexTrade('cancelall', msg)
            self.sendMsgToBitmexTrade('cancelall', msg)
        elif market == 'okex':
            self.sendMsgToOkexTrade('cancelall', msg)
        elif market == 'bitmex':
            self.sendMsgToBitmexTrade('cancelall', msg)
    # 获取费率
    # {type:funding}
    def getBitmexFunding(self):
        msg = {'type':'funding'}
        self.sendMsgToBitmexTrade('funding', msg)
    
    # 帐户
    # 获取帐户信息
    # {type:account}
    def getAccount(self):
        msg = {'type':'account'}
        self.sendMsgToOkexTrade('account', msg)
        self.sendMsgToBitmexTrade('account', msg)
    # 提现
    # {type:withdraw,addr:地址,amount:数量,price:支付手续费,cointype:btc}
    # okex资金划转
    # {type:transfer,amount:数量,from:从那个资金帐户划转,to:划转到那个资金帐户,cointype:btc}
    def setTradeTest(self,isTest):
        msg = {'type':'test','test':isTest}
        self.sendMsgToOkexTrade('test', msg)
        self.sendMsgToBitmexTrade('test', msg)
    #收到数据   
    #okex数据

    def onOkexData(self,datadic):
        if 'type' in datadic and datadic['type'] == 'pong':
            self.socketstate['od'] = True
            print('pong from okex ws data server...')
        elif type(datadic) == list and 'channel' in datadic[0] and datadic[0]['channel'] == 'ok_sub_futureusd_btc_depth_quarter_5':
            # print(datadic)
            data = datadic[0]['data']
            self.sells5 = data['asks'][::-1]
            self.buys5 = data['bids']
            self.okexDatas = [self.buys5[0],self.sells5[0],int(time.time())]             #买一价，卖一价，接收数据时间
            self.updateDataSub()
            # print(self.buys5[0],self.sells5[0])
        
        elif type(datadic) == list and 'channel' in datadic[0] and datadic[0]['channel'] == 'ok_sub_futureusd_trades':
            #合约定单数据更新
# amount(double): 委托数量
# contract_name(string): 合约名称
# created_date(long): 委托时间
# create_date_str(string):委托时间字符串
# deal_amount(double): 成交数量
# fee(double): 手续费
# order_id(long): 订单ID
# price(double): 订单价格
# price_avg(double): 平均价格
# status(int): 订单状态(0等待成交 1部分成交 2全部成交 -1撤单 4撤单处理中)
# symbol(string): btc_usd   ltc_usd   eth_usd   etc_usd   bch_usd
# type(int): 订单类型 1：开多 2：开空 3：平多 4：平空
# unit_amount(double):合约面值
# lever_rate(double):杠杆倍数  value:10/20  默认10
# system_type(int):订单类型 0:普通 1:交割 2:强平 4:全平 5:系统反单
        # [{u'binary': 0, u'data': 
        #{u'orderid': 1270246017934336, 
        #u'contract_name': u'BTC0928', 
        #u'fee': 0.0, 
        #u'user_id': 2051526, 
        #u'contract_id': 201809280000012, 
        #u'price': 1000.0, 
        #u'create_date_str': u'2018-08-13 08:00:16', 
        #u'amount': 1.0, 
        #u'status': 0, 
        #u'system_type': 0, 
        #u'unit_amount': 100.0, 
        #u'price_avg': 0.0, 
        #u'contract_type': u'quarter', 
        #u'create_date': 1534118416047, 
        #u'lever_rate': 20.0, 
        #u'type': 1, 
        #u'deal_amount': 0.0}, 
        #u'channel': u'ok_sub_futureusd_trades'}]
            print(datadic)
        
        elif type(datadic) == list and 'channel' in datadic[0] and datadic[0]['channel'] == 'ok_sub_futureusd_userinfo':
            #用户帐户数据更新
# 全仓信息
# balance(double): 账户余额
# symbol(string)：币种
# keep_deposit(double)：保证金
# profit_real(double)：已实现盈亏
# unit_amount(int)：合约价值
# 逐仓信息
# balance(double):账户余额
# available(double):合约可用
# balance(double):合约余额
# bond(double):固定保证金
# contract_id(long):合约ID
# contract_type(string):合约类别
# freeze(double):冻结
# profit(double):已实现盈亏
# unprofit(double):未实现盈亏
# rights(double):账户权益
        #[{u'binary': 0,
        # u'data': {
            #u'contracts': [
                #{u'available': 0.01223452, 
                #u'bond': 0.0, 
                #u'contract_id': 201809280000012, 
                #u'profit': 0.0, 
                #u'freeze': 0.005, 
                #u'long_order_amount': 0.0, 
                #u'short_order_amount': 0.0, 
                #u'balance': 0.0, 
                #u'pre_short_order_amount': 0.0, 
                #u'pre_long_order_amount': 1.0}], 
            #u'symbol': u'btc_usd',
            # u'balance': 0.01723452},
        # u'channel': u'ok_sub_futureusd_userinfo'}]
            print(datadic)
    
        elif type(datadic) == list and 'channel' in datadic[0] and datadic[0]['channel'] == 'ok_sub_futureusd_positions':
            #ok_sub_futureusd_positions,仓位数据更新
# 全仓说明
# position(string): 仓位 1多仓 2空仓
# contract_name(string): 合约名称
# costprice(string): 开仓价格
# bondfreez(string): 当前合约冻结保证金
# avgprice(string): 开仓均价
# contract_id(long): 合约id
# position_id(long): 仓位id
# hold_amount(string): 持仓量
# eveningup(string): 可平仓量
# margin(double): 固定保证金
# realized(double):已实现盈亏

# 逐仓说明
# contract_id(long): 合约id
# contract_name(string): 合约名称
# avgprice(string): 开仓均价
# balance(string): 合约账户余额
# bondfreez(string): 当前合约冻结保证金
# costprice(string): 开仓价格
# eveningup(string): 可平仓量
# forcedprice(string): 强平价格
# position(string): 仓位 1多仓 2空仓
# profitreal(string): 已实现盈亏
# fixmargin(double): 固定保证金
# hold_amount(string): 持仓量
# lever_rate(double): 杠杆倍数
# position_id(long): 仓位id
# symbol(string): btc_usd   ltc_usd   eth_usd   etc_usd   bch_usd  eos_usd  xrp_usd btg_usd 
# user_id(long):用户ID
    #[{u'binary': 0, u'data': 
        #{u'positions': 
            #[{u'contract_name': u'BTC0928',
            # u'balance': 0.0, u'contract_id': 201809280000012, 
            #u'fixmargin': 0, u'position_id': 1157028442213376, 
            #u'avgprice': 0, u'eveningup': 0, u'profitreal': 0.0,
            # u'hold_amount': 0, u'costprice': 0, 
            #u'position': 1, u'lever_rate': 10, 
            #u'bondfreez': 0.005, u'forcedprice': 0}, 
        #{u'contract_name': u'BTC0928', u'balance': 0.0, 
            #u'contract_id': 201809280000012, u'fixmargin': 0, 
            #u'position_id': 1157028442213376, u'avgprice': 0, 
            #u'eveningup': 0, u'profitreal': 0.0, u'hold_amount': 0, 
            #u'costprice': 0, u'position': 2, u'lever_rate': 10, 
            #u'bondfreez': 0.005, u'forcedprice': 0}, 
        #{u'contract_name': u'BTC0928', u'balance': 0.0, 
            #u'contract_id': 201809280000012, u'fixmargin': 0.0, 
            #u'position_id': 1157028442213376, u'avgprice': 7070.17, 
            #u'eveningup': 0.0, u'profitreal': 0.0, u'hold_amount': 0.0, 
            #u'costprice': 7070.17, u'position': 1, u'lever_rate': 20, 
            #u'bondfreez': 0.005, u'forcedprice': 0.0}, 
        #{u'contract_name': u'BTC0928', u'balance': 0.0, 
            #u'contract_id': 201809280000012, u'fixmargin': 0.0, 
            #u'position_id': 1157028442213376, u'avgprice': 7834.0, 
            #u'eveningup': 0.0, u'profitreal': 0.0, u'hold_amount': 0.0, 
            #u'costprice': 7834.0, u'position': 2, u'lever_rate': 20,
            # u'bondfreez': 0.005, u'forcedprice': 0.0}], u'symbol': u'btc_usd',
            # u'user_id': 2051526}, 
    #u'channel': u'ok_sub_futureusd_positions'}]
            print(datadic)
        self.lastimedic['od'] = int(time.time())
    #交易下单返回状态
    def onOkexTradeBack(self,datadic):
        if 'type' in datadic and datadic['type'] == 'pong':
            self.socketstate['ot'] = True
            print('pong from okex trade http server...')
        else:
            print(datadic)
        self.lastimedic['ot'] = int(time.time())

    #bitmex数据
    def onBitmexData(self,datadic):
        if 'type' in datadic and datadic['type'] == 'pong':
            self.socketstate['bd'] = True
            print('pong from bitmex ws data server...')
        elif 'table' in datadic and datadic['table'] == 'quote':
            datas = datadic['data']
            timeint,timestr = self.timeconvent(datas[-1]['timestamp'])
            self.selltop = [datas[-1]['askPrice'],datas[-1]['askSize'],timeint,timestr]
            self.buytop = [datas[-1]['bidPrice'],datas[-1]['bidSize'],timeint,timestr]
            self.bitmexDatas = [self.buytop,self.selltop,self.buytop[2]]           #买一价，卖一价, 接收数据时间
            self.updateDataSub()
            # print(self.buytop,self.selltop)
        elif 'table' in datadic and datadic['table'] == 'execution': #// 个别成交，可能是多个成交
            print('---execution--bitmex--')
            print(datadic)
        elif 'table' in datadic and datadic['table'] == 'order': #// 你委托的更新
            print('---order--bitmex--')
            # {u'action': u'insert', u'table': u'order', u'data': [{u'ordStatus': u'New', u'exDestination': u'XBME', u'text': u'Submitted via API.', u'timeInForce': u'GoodTillCancel', u'currency': u'USD', u'pegPriceType': u'', u'simpleLeavesQty': 0.0158, u'ordRejReason': u'', u'transactTime': u'2018-08-12T23:02:44.540Z', u'clOrdID': u'os-2-1534114964.188801', u'settlCurrency': u'XBt', u'cumQty': 0, u'displayQty': None, u'avgPx': None, u'price': 6340, u'simpleOrderQty': None, u'contingencyType': u'', u'triggered': u'', u'timestamp': u'2018-08-12T23:02:44.540Z', u'symbol': u'XBTUSD', u'pegOffsetValue': None, u'execInst': u'ParticipateDoNotInitiate', u'simpleCumQty': 0, u'orderID': u'13c79094-518a-c95b-fd95-3f090d339e6e', u'multiLegReportingType': u'SingleSecurity', u'account': 278343, u'stopPx': None, u'leavesQty': 100, u'orderQty': 100, u'workingIndicator': False, u'ordType': u'Limit', u'clOrdLinkID': u'', u'side': u'Sell'}]}
            #下单后websocket返回的状态改变数据
            # {u'action': u'update', u'table': u'order', u'data': [{u'orderID': u'71931c93-340d-9455-bf80-b0ac50797604', u'account': 278343, u'workingIndicator': True, u'timestamp': u'2018-08-12T21:13:37.105Z', u'symbol': u'XBTUSD', u'clOrdID': u''}]}
            #取消定单时的websocket返回的状态改变数据
            #{u'action': u'update', u'table': u'order', u'data': [{u'orderID': u'71931c93-340d-9455-bf80-b0ac50797604', u'account': 278343, u'ordStatus': u'Canceled', u'workingIndicator': False, u'text': u'Canceled: Canceled via API.\nSubmitted via API.', u'symbol': u'XBTUSD', u'leavesQty': 0, u'simpleLeavesQty': 0, u'timestamp': u'2018-08-12T21:15:44.581Z', u'clOrdID': u''}]}
            print(datadic)
            if 'ordStatus' in datadic['data'][0] and datadic['data'][0]['ordStatus'] == 'Canceled':#定单已取消
                self.onBitmexOrderCancelOK(datadic['data'][0])
            elif 'ordStatus' not in datadic['data'][0] and datadic['data'][0]['workingIndicator']:
                self.onBitmexOrderOnline(datadic['data'][0]) #定单成功委托
            elif datadic['action'] == 'insert':#新增定单
                self.onBitmexOrderStart(datadic['data'][0])
        elif 'table' in datadic and datadic['table'] == 'margin': #你账户的余额和保证金要求的更新
            print('---margin--bitmex--')
            print(datadic)
        elif 'table' in datadic and datadic['table'] == 'position': #// 你仓位的更新
            print('---position--bitmex--')
            print(datadic)
        else:
            print('---other--bitmex--')
            print(datadic)
        self.lastimedic['bd'] = int(time.time())

    #bitmex新增加定单委托
    def onBitmexOrderStart(self,data):
        if data['ordStatus'] == 'New':
            print('新增定单,cid:%s'%(data['clOrdID']))
            if data['ordStatus']['workingIndicator']:
                self.onBitmexOrderOnline(data) #定单已成功委托
    #当下单已成功委托
    def onBitmexOrderOnline(self,data):
        if data['clOrdID'] in self.bCIDData:
            self.bCIDData[data['clOrdID']]['state'] = 1
        else:
            print("非交易对下单，已成功委托的定单ID为bitmex下单服务器自动生成,")
            print(data)
    #当bitmex下单完全成交
    def onBitmexTradeOK(self,data):
        if data['clOrdID'] in self.bCIDData:
            self.bCIDData[data['clOrdID']]['state'] = 2
            ptype = self.okexTradeMsgs.pop(0)
            ocid = data['clOrdID']
            if ptype == 'ol':
                msg = {'type':'ol','amount':self.baseAmount,'price':self.okexDatas[1][0],'islimit':1,'cid':ocid}
                self.oCIDData = {'msg':msg,'state':0}
                self.sendMsgToOkexTrade('ol', msg)
            elif ptype == 'os':
                msg = {'type':'os','amount':self.baseAmount,'price':self.okexDatas[0][0],'islimit':1,'cid':ocid}
                self.oCIDData = {'msg':msg,'state':0}
                self.sendMsgToOkexTrade('os', msg)
            elif ptype == 'cl':
                msg = {'type':'cl','amount':self.baseAmount,'price':self.okexDatas[0][0],'islimit':1,'cid':ocid}
                self.oCIDData = {'msg':msg,'state':0}
                self.sendMsgToOkexTrade('cl', msg)
            elif ptype == 'cs':
                msg = {'type':'cs','amount':self.baseAmount,'price':self.okexDatas[1][0],'islimit':1,'cid':ocid}
                self.oCIDData = {'msg':msg,'state':0}
                self.sendMsgToOkexTrade('cs', msg)
        else:
            print("非交易对下单，完全成交的定单ID为bitmex下单服务器自动生成,")
            print(data)
    #当bitmex定单取消成功
    def onBitmexOrderCancelOK(self,data):
        if data['clOrdID'] in self.bCIDData:
            tmpobj = self.bCIDData.pop(data['clOrdID'])
            msg = tmpobj['msg']
            deln  = -1
            for n in range(len(self.okexTradeMsgs)):
                d = self.okexTradeMsgs[n]
                if d['cid'] == msg['cid']:
                    deln = n
                    break
            if deln >= 0:
                self.okexTradeMsgs.pop(deln)
        else:
            print("非交易对下单，已成功取消的定单ID为bitmex下单服务器自动生成,")
            print(data)

    #bitmex下单服务器反回下单情况
    def onBitmexTradeBack(self,datadic):
        if 'type' in datadic and datadic['type'] == 'pong':
            self.socketstate['bt'] = True
            print('pong from bitmex trade http server...')
        else:
            print(datadic)

        self.lastimedic['bt'] = int(time.time())


    
    # self.initBitmexDataSocket()
    def sendMsgToBitmexData(self,ptype,msg,isSigned = False):
        try:
            if self.bitmexDataSocket:
                if isSigned:
                    outobj = {'type':ptype,'time':int(time.time()),'sign':'issigned','data':msg}
                    outstr = json.dumps(outobj)
                    self.bitmexDataSocket.send(outstr.encode())
                else:
                    ptime = int(time.time())
                    sign = signTool.signMsg(msg,ptime,self.bitmexSeckey)
                    outobj = {'type':ptype,'time':ptime,'sign':sign,'data':msg}
                    outstr = json.dumps(outobj)
                    self.bitmexDataSocket.send(outstr.encode())
                return True
            else:
                print("没有bitmexDataSocket客户端连接")
                self.initBitmexDataSocket()
                return False
        except Exception as e:
            print('服务器端bitmexDataSocket网络错误1')
            return False

    # self.initBitmexTradeSocket()
    def sendMsgToBitmexTrade(self,ptype,msg,isSigned = False):
        try:
            if self.bitmexTradeSocket:
                if isSigned:
                    outobj = {'type':ptype,'time':int(time.time()),'sign':'issigned','data':msg}
                    outstr = json.dumps(outobj)
                    self.bitmexTradeSocket.send(outstr.encode())
                else:
                    ptime = int(time.time())
                    sign = signTool.signMsg(msg,ptime,self.bitmexSeckey)
                    outobj = {'type':ptype,'time':ptime,'sign':sign,'data':msg}
                    outstr = json.dumps(outobj)
                    self.bitmexTradeSocket.send(outstr.encode())
                return True
            else:
                print("没有bitmexTradeSocket客户端连接")
                self.initBitmexTradeSocket()
                return False
        except Exception as e:
            print('服务器端bitmexTradeSocket网络错误1')
            return False
    
    # self.initOkexDataSocket()
    def sendMsgToOkexData(self,ptype,msg,isSigned = False):
        try:
            if self.okexDataSocket:
                if isSigned:
                    outobj = {'type':ptype,'time':int(time.time()),'sign':'issigned','data':msg}
                    outstr = json.dumps(outobj)
                    self.okexDataSocket.send(outstr.encode())
                else:
                    ptime = int(time.time())
                    sign = signTool.signMsg(msg,ptime,self.okexSeckey)
                    outobj = {'type':ptype,'time':ptime,'sign':sign,'data':msg}
                    outstr = json.dumps(outobj)
                    self.okexDataSocket.send(outstr.encode())
                return True
            else:
                print("没有okexDataSocket客户端连接")
                self.initOkexDataSocket()
                return False
        except Exception as e:
            print('服务器端okexDataSocket网络错误1')
            return False

    # self.initOkexTradeSocket()
    def sendMsgToOkexTrade(self,ptype,msg,isSigned = False):
        try:
            if self.okexTradeSocket:
                if isSigned:
                    outobj = {'type':ptype,'time':int(time.time()),'sign':'issigned','data':msg}
                    outstr = json.dumps(outobj)
                    self.okexTradeSocket.send(outstr.encode())
                else:
                    ptime = int(time.time())
                    sign = signTool.signMsg(msg,ptime,self.okexSeckey)
                    outobj = {'type':ptype,'time':ptime,'sign':sign,'data':msg}
                    outstr = json.dumps(outobj)
                    self.okexTradeSocket.send(outstr.encode())
                return True
            else:
                print("没有okexDataSocket客户端连接")
                self.initOkexTradeSocket()
                return False
        except Exception as e:
            print('服务器端okexDataSocket网络错误1')
            return False
    
    #当有客户端30秒没有接收到数据时就发送ping
    def pingAllServer(self,ptimeDelay = 30):
        ptime = int(time.time())
        for k in self.socketstate.keys():
            if ptime - self.lastimedic[k] > ptimeDelay:
                self.socketstate[k] = False
            else:
                self.socketstate[k] = True
        if not self.socketstate['bd']:
            self.sendMsgToBitmexData('ping','ping',isSigned = True)
        if not self.socketstate['bt']:
            self.sendMsgToBitmexTrade('ping','ping',isSigned = True)
        if not self.socketstate['od']:
            self.sendMsgToOkexData('ping','ping',isSigned = True)
        if not self.socketstate['ot']:
            self.sendMsgToOkexTrade('ping','ping',isSigned = True)
    def printSet(self):
        print 'isTest:',self.isTest
        print 'amount:',self.amount

    def cleanAllTrade(self):
        pass


def main():
     pass
if __name__ == '__main__':
    main()
   
