#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2018-05-24 15:13:31
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$
#创建SocketServerTCP服务器：

import os,sys
import bitmexWebSocket
import threading
import time

from sys import version_info  
if version_info.major < 3:
    import SocketServer as socketserver
else:
    import socketserver

import socket
import json

from magetool import pathtool

nfpth = os.path.abspath(__file__)
ndir,_ = os.path.split(nfpth)
pdir = pathtool.GetParentPath(ndir)
ppdir = pathtool.GetParentPath(pdir) + os.sep + 'util'
sys.path.append(ppdir)
import apikeytool
import signTool

myname = socket.getfqdn(socket.gethostname())
myaddr = socket.gethostbyname(myname)

print('selfip:%s'%(myaddr))
host = str(myaddr)


port = apikeytool.apikeydic['bitmex']['wsport']
host = apikeytool.apikeydic['bitmex']['wsaddr']
addr = (host,port)


tradetool = None


class Servers(socketserver.StreamRequestHandler):
    def handle(self):
        global tradetool
        tradetool.setSocketClient(self.request)
        print('got connection from ',self.client_address)
        while True:
            try:  
                data = self.request.recv(4096)
            except EOFError:  
                print('接收客户端错误，客户端已断开连接,错误码:')
                print(EOFError )
                break
            except:  
                print('接收客户端错误，客户端已断开连接')
                break
            if not data: 
                break
            data = data.decode()
            print('data len:%d'%(len(data)))
            print("RECV from ", self.client_address)
            print(data)
            dicdata = json.loads(data)
            #来自其他服务器的数据要求验证签名
            #数据格式:{"type":消息类型,"sign":sha256的data转为字符串的签名,"time":时间戳用来确定发送时间和验证签名,"data":{消息正文内容}}
            #目前数据只验证签名，未作加密处理，后期加入数据加密后传送
            #{"sign":"test3","time":123456,"data":{"a":123}}
            if signTool.isSignOK(dicdata,tradetool.secret):
                tradetool.reciveMsgFromClient(dicdata)
            elif dicdata['type'] == 'ping':
                self.request.send('{"type":"pong","erro":"0"}'.encode())
            else:
                self.request.send('{"erro":"signErro"}'.encode())

            # self.request.send('aaa')

def startServerThread():
    server = socketserver.ThreadingTCPServer(addr,Servers,bind_and_activate = False)
    server.allow_reuse_address = True   #设置IP地址和端口可以不使用客户端连接等待，并手动绑定服务器地址和端口，手动激活服务器,要不然每一次重启服务器都会出现端口占用的问题
    server.server_bind()
    server.server_activate()
    print('server started:')
    print(addr)
    server.serve_forever()

def startDataThread():
    global tradetool
    apikey = apikeytool.apikeydic['bitmex']['apikey']
    secretkey = apikeytool.apikeydic['bitmex']['secretkey']
    tradetool = bitmexWebSocket.bitmexWSTool(apikey,secretkey)
    tradetool.wsRunForever()

def start_server():
    thr2 = threading.Thread(target=startDataThread,args=())
    thr2.setDaemon(True)
    thr2.start()
    thr = threading.Thread(target=startServerThread,args=())
    thr.setDaemon(True)
    thr.start()

def removeLogFile():
    if os.path.exists('bitmexdeep.txt'):
        os.remove('bitmexdeep.txt')

def main():
    removeLogFile()
    start_server()
    while True:
        time.sleep(60)

#测试
if __name__ == '__main__':
    main()
    
    