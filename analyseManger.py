#!/usr/bin/python
# -*- coding: utf-8 -*-
# encoding: utf-8
#客户端调用，用于查看API返回结果

import os,sys
import socket
import threading
import time
import json

from magetool import pathtool
sys.path.append('util')
import signTool



def sayMsg(msg):
    cmd = 'say %s'%(msg)
    os.system(cmd)
    print msg


class TradeTool(object):
    """docstring for ClassName"""
    def __init__(self,configdic,isTest = True):
        #期货交易工具
        self.configdic = configdic
        self.isTest = isTest

        self.initTraddeConfig()

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

        self.initSocket()

        

    #初始化交易参数,如单次下单合约值，谁主动成交，谁被动成交,交易手续费等
    def initTraddeConfig(self):
        pass

    def initSocket(self):
        isErro = False
        try:
            print('connecting okex http trade server:',self.configdic['okex']['httpaddr'],self.configdic['okex']['httpport'])
            self.okexTradeSocket = socket.socket()  # instantiate
            self.okexTradeSocket.connect((self.configdic['okex']['httpaddr'], self.configdic['okex']['httpport']))  # connect to the server
            print('okex http trade server connected!')
            def okexTradeRun():
                while True:
                    data = self.okexTradeSocket.recv(4096)
                    datadic = json.loads(data.decode())
                    self.onOkexTradeBack(datadic)
            self.okexTradethr = threading.Thread(target=okexTradeRun,args=())
            self.okexTradethr.setDaemon(True)
            self.okexTradethr.start()
            self.socketstate['ot'] = True
        except Exception as e:
            print('connect okex http trade server erro...')
            self.okexTradeSocket = None
            isErro =  True
        try:
            print('connecting okex ws data server:',self.configdic['okex']['wsaddr'],self.configdic['okex']['wsport'])
            self.okexDataSocket = socket.socket()  # instantiate
            self.okexDataSocket.connect((self.configdic['okex']['wsaddr'], self.configdic['okex']['wsport']))  # connect to the server
            print('okex ws data server connected!')
            def okexDataRun():
                while True:
                    data = self.okexDataSocket.recv(4096)
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
        try:
            print('connecting bitmex Trade data server:',self.configdic['bitmex']['httpaddr'],self.configdic['bitmex']['httpport'])
            self.bitmexTradeSocket = socket.socket()  # instantiate
            self.bitmexTradeSocket.connect((self.configdic['bitmex']['httpaddr'], self.configdic['bitmex']['httpport']))  # connect to the server
            print('bitmex ws Trade server connected!')
            def okexDataRun():
                while True:
                    data = self.bitmexTradeSocket.recv(4096)
                    datadic = json.loads(data.decode())
                    self.onBitmexTradeBack(datadic)
            self.bitmexTradethr = threading.Thread(target=okexDataRun,args=())
            self.bitmexTradethr.setDaemon(True)
            self.bitmexTradethr.start()
            self.socketstate['bt'] = True
        except Exception as e:
            print('connect erro bitmex trade...')
            self.bitmexTradeSocket = None
            isErro =  True
        try:
            print('connecting bitmex ws data server:',self.configdic['bitmex']['wsaddr'],self.configdic['bitmex']['wsport'])
            self.bitmexDataSocket = socket.socket()  # instantiate
            self.bitmexDataSocket.connect((self.configdic['bitmex']['wsaddr'], self.configdic['bitmex']['wsport']))  # connect to the server
            print('bitmex ws data server connected!')
            def bitmexDataRun():
                while True:
                    data = self.bitmexDataSocket.recv(4096)
                    datadic = json.loads(data.decode())
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
    #收到数据
    #okex数据
    def onOkexData(self,datadic):
        if datadic['type'] == 'pong':
            self.socketstate['od'] = True
            print('pong from okex ws data server...')
        else:
            print(datadic)
    #交易下单返回状态
    def onOkexTradeBack(self,datadic):
        if datadic['type'] == 'pong':
            self.socketstate['ot'] = True
            print('pong from okex trade http server...')
        else:
            print(datadic)

    #bitmex数据
    def onBitmexData(self,datadic):
        if datadic['type'] == 'pong':
            self.socketstate['bd'] = True
            print('pong from bitmex ws data server...')
        else:
            print(datadic)
    def onBitmexTradeBack(self,datadic):
        if datadic['type'] == 'pong':
            self.socketstate['bt'] = True
            print('pong from bitmex trade http server...')
        else:
            print(datadic)

    #更新交易状态
    def updateTradeState(self):
        pass

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
            else:
                print("没有bitmexDataSocket客户端连接")
        except Exception as e:
            print('服务器端bitmexDataSocket网络错误1')

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
            else:
                print("没有bitmexTradeSocket客户端连接")
        except Exception as e:
            print('服务器端bitmexTradeSocket网络错误1')

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
            else:
                print("没有okexDataSocket客户端连接")
        except Exception as e:
            print('服务器端okexDataSocket网络错误1')

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
            else:
                print("没有okexDataSocket客户端连接")
        except Exception as e:
            print('服务器端okexDataSocket网络错误1')
    
    def pingAllServer(self):
        for k in self.socketstate.keys():
            self.socketstate[k] = False
        self.sendMsgToBitmexData('ping','ping',isSigned = True)
        self.sendMsgToBitmexTrade('ping','ping',isSigned = True)
        self.sendMsgToOkexData('ping','ping',isSigned = True)
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
   