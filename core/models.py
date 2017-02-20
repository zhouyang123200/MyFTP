#!/usr/bin/python
# -*- coding: utf-8 -*-
# __author__: Administrator
# __date__  : 2016/10/8

import socketserver
import socket
import pickle
import os
import threading
import sys
import prompt_toolkit
import time
from core import  logger
from uuid import uuid1
from conf import settings

global order

class usr_service:
    '''
    用于处理用户的指令
    '''
    def __init__(self,usr,conn,logger,address):
        self.usr = usr
        self.conn = conn
        self.logger = logger
        self.address = address
        self.current_path = None

    def service(self):
        '''
        用于把用户传过来的指令转化为自己要执行的函数
        :return: None
        '''
        choice_dict = {
            'post': self.post,
            'download': self.download,
            'cd': self.open_dir,
            'rm': self.rm,
            'ls': self.ls,
            'mkdir': self.mkdir
        }

        self.show_dirs()
        while True:
            try:
                command,args = self.recv_cmd()
            except ConnectionRefusedError:
                break
            if command in choice_dict:
                choice_dict[command](args)
            else:
                if command == '':
                    self.logger.info('用户%s终止链接'%str(self.address))
                    break
                print('客户端命令错误 %s'%command)
                break

    def open_dir(self,args):
        '''
        打开文件目录
        :param args: 文件目录
        :return: None
        '''
        path, = args
        print('正打开目录 %s'%path)
        if path == '..':
            if self.current_path == self.usr.usr_path:
                pass
            else:
                self.current_path = os.path.dirname(self.current_path)
            self.show_dirs(self.current_path)
        elif os.path.isdir(os.path.join(self.current_path,path)):
            self.current_path = os.path.join(self.current_path,path)
            self.show_dirs(self.current_path)
        else:
            message = '文件系统异常'
            self.conn.sendall(bytes(message,'utf-8'))
            message = self.conn.recv(1024)
            print('打开文件异常')

    def ls(self,args):
        '''
        直接调用显示文件目录的函数
        :param args: 任意值，只规定了显示当前目录
        :return: None
        '''
        self.show_dirs(self.current_path)

    def post(self,args):
        '''
        文件上传函数，每传送1024个文件字节后，还要传送5个字节的命令用于断点续传
        :param args: 文件名
        :return: None
        '''
        filename, = args
        filepath = os.path.join(self.current_path,filename)
        # print(filepath)
        if os.path.isfile(filepath):    # 判断目录下是否存在此文件
            filesize = os.path.getsize(filepath)    # 得到文件的大小，再发送给客户端
            message = 'restart' + ' ' + str(filesize)
            self.conn.sendall(bytes(message,'utf-8'))
            message = self.conn.recv(1024)
            size = int(message.decode('utf-8'))
            if filesize == size:    # 如果文件大小相等，则不用传送
                self.conn.sendall(bytes('completed','utf-8'))
                return None
            elif filesize < size:
                self.conn.sendall(bytes('send','utf-8'))
                print('继续传输上一个文件')
                with open(filepath,'ab') as f:
                    while filesize != size:
                        data = self.conn.recv(1024)
                        f.write(data)
                        filesize += len(data)
                        self.conn.sendall(bytes('ok','utf-8'))  # 用于检测通讯状态正常
                        message = self.conn.recv(5).decode('utf-8') # 接收大小为5个字节的指令，判断上传是否继续
                        if message == 'pause':  # 暂停
                            print('客户端暂停一个文件的传输')
                            self.logger.info('用户%s暂停了一个上传'%self.usr.name)
                            break
                        elif message == 'go on': # 继续
                            pass
                    else:
                        print('完成一个文件传输')
                        self.logger.info('用户%s 完成了文件 %s 的上传' %(self.usr.name,filename))
            else:
                self.conn.sendall(bytes('文件大小错误', 'utf-8'))
                return None
        else:   # 没有此文件，从开始位置上传
            self.conn.sendall(bytes('start 0','utf-8'))
            with open(filepath, 'wb') as f:
                size = int(self.conn.recv(1024).decode('utf-8'))
                print('接收文件大小 %s'%size)
                filesize = 0

                while filesize != size:
                    data = self.conn.recv(1024)
                    f.write(data)
                    filesize += len(data)
                    self.conn.sendall(bytes('ok','utf-8'))
                    message = self.conn.recv(5).decode('utf-8')
                    if message == 'pause':
                        print('客户端暂停一个文件的传输')
                        self.logger.info('用户%s暂停了一个上传' % self.usr.name)
                        break
                    elif message == 'go on':
                        pass
                else:
                    print('完成一个文件传输')
                    self.logger.info('用户%s 完成了文件 %s 的上传' % (self.usr.name, filename))

    def rm(self,args):
        '''
        删除文件或文件夹
        :param args: 文件名或目录名
        :return:
        '''
        _path, = args
        print('正在删除文件 %s'%_path)
        path = os.path.join(self.current_path, _path)
        try:
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
        except OSError as e:
            self.conn.sendall(bytes(e, 'utf-8'))
            message = self.conn.recv(2).decode('utf-8')
            if message != 'ok':
                print('通信出现错误')
        else:
            self.show_dirs(self.current_path)
            self.logger.info('用户%s 删除了文件 %s ' % (self.usr.name, _path))

    def mkdir(self,args):
        dirname, = args
        try:
            os.mkdir(os.path.join(self.current_path,dirname))
            message = '创建目录 %s'%dirname
            self.conn.sendall(bytes(message,'utf-8'))
        except Exception as e:
            self.conn.sendall(bytes(str(e),'utf-8'))

    def download(self,args):
        '''
        下载文件
        :param args: 文件名
        :return:
        '''
        filename,size =args
        filepath = os.path.join(self.current_path,filename)
        size = int(size)
        print(filepath)
        if os.path.isfile(filepath):    # 先判断文件是否存在
            filesize = os.path.getsize(filepath)
            self.conn.sendall(bytes(str(filesize),'utf-8')) # 把文件大小发送客户端
            message = self.conn.recv(16).decode('utf-8')    # 接收客户端文件状态
            if message == 'completed':
                pass
            elif message == 'start':
                with open(filepath,'rb') as f:
                    f.seek(size)
                    while size != filesize:
                        data = f.read(1024)
                        self.conn.sendall(data)
                        size += len(data)
                        message = self.conn.recv(5).decode('utf-8')
                        if message == 'go on':
                            pass
                        elif message == 'pause':
                            self.logger.info('用户%s暂停了一个下载' % self.usr.name)
                            break
                        else:
                            print('文件传输异常')
                            self.conn.close()
                            break
                    else:
                        print('文件下载完成')
                        self.logger.info('用户%s 完成了文件 %s 的下载' % (self.usr.name, filename))
        else:
            self.conn.sendall(bytes('00','utf-8'))

    def show_dirs(self,current_path=None):
        if not current_path:
            self.current_path = self.usr.usr_path
            current_path = self.usr.usr_path

        dir_list = os.listdir(current_path)
        dir_str = '文件夹：\n'
        file_str = '文件：\n'
        for item in dir_list:
            if os.path.isdir(os.path.join(current_path,item)):
                dir_str = dir_str + '\t' + item + '\n'
            elif os.path.isfile(os.path.join(current_path,item)):
                file_str = file_str + '\t' + item + '\n'
            else:
                raise Exception('存在文件系统错误')
        message = dir_str + '\n' + file_str

        if not dir_str and not file_str:
            message = '此目录还没有任何文件'

        message = bytes(message,'utf-8')
        self.conn.sendall(message)
        flag = self.conn.recv(2)
        if flag.decode('utf-8') == 'ok':
            pass
        else:
            print('文件目录传输异常')

    def recv_cmd(self):
        client_data = self.conn.recv(1024)
        client_data = client_data.decode('utf-8')
        command,*args = client_data.split(' ')
        return (command,args)

    def error_echo(self,command):
        message = '用户指令错误:%s'%command
        self.conn.sendall(bytes(message,'utf-8'))
        flag = self.conn.recv(1024)

class FTPServerHandler(socketserver.BaseRequestHandler):
    '''
    处理客户端请求
    '''
    def handle(self):
        hand_logger = logger.logger('handler_logger')
        conn = self.request
        hand_logger.info('服务端开始处理 %s 的请求'%str(self.client_address))
        usr = log_in(conn)  # 把套接字传给 log_in 函数用于登录
        if usr: # 如果登录成功则返回一个usr对象
            server_obj = usr_service(usr,conn,hand_logger,self.client_address)
            server_obj.service()

class user:
    def __init__(self,name,password):
        self.name = name
        self.password = password
        self.nid = uuid1()  # 用于生成用户一个唯一识别
        self.usr_path = os.path.join(settings.usr_filedata_path,str(self.nid))
        os.makedirs(os.path.join(settings.usr_filedata_path,str(self.nid))) # 创建用户存储文件的目录

    def save(self):
        '''
        使用pickle用于保存用户实例
        :return:
        '''
        nid = str(self.nid)
        if not os.path.isdir(settings.usr_data_path):
            os.makedirs(settings.usr_data_path)
        file_path = os.path.join(settings.usr_data_path, nid)
        pickle.dump(self, open(file_path, 'wb'))

    @staticmethod
    def get_all_list():
        '''
        得到所有用户实例
        :return: 一个列表
        '''
        ret = []
        for item in os.listdir(os.path.join(settings.usr_data_path)):
            obj = pickle.load(open(os.path.join(settings.usr_data_path, item), 'rb'))
            ret.append(obj)
        return ret

class client_soft:
    '''
    客户端使用的各项服务
    '''
    def __init__(self,address):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect(settings.address)

    def run(self):
        '''
        一个循环，处理用户输入的各种指令
        :return:
        '''
        if self.log_in():
            s = '------------ 你已进入文件系统-----------'
            print(s)
            self.show_dirs()    # 首先显示服务端发送过来的目录信息
            while True:
                global order
                order = prompt_toolkit.shortcuts.prompt('\n>>>',patch_stdout=True)
                # 使用了命令行工具，使其它线程不破坏主线程的输入
                if order == 'pause':
                    continue
                if len(order.split(' ')) == 1:
                    command = order
                    if command not in ('quit', 'ls'):
                        continue
                    getattr(self, command)()
                else:
                    command,*args = order.split(' ')
                    if command not in ('post','download','cd','rm','mkdir'):
                        continue
                    fun = getattr(self,command) # 使用反射
                    t = threading.Thread(target=fun,args=(args,))   # 开启线程去执行功能函数
                    t.setDaemon(True)
                    t.start()
        else:
            pass

    def show_dirs(self):
        message = self.conn.recv(1024)
        print(message.decode('utf-8'))
        self.conn.sendall(bytes('ok','utf-8'))

    def mkdir(self, args):
        '''
        创建目录
        :param args: 目录名
        :return:
        '''
        dirname, = args
        message = 'mkdir' + ' ' + dirname
        self.conn.sendall(bytes(message, 'utf-8'))
        message = self.conn.recv(1024)
        print(message.decode('utf-8'))

    def post(self,args):
        filename, = args
        filepath = os.path.join(settings.download_path,filename)
        if os.path.isfile(filepath):
            message = 'post' + ' ' + ' '.join(args)
            self.conn.sendall(bytes(message, 'utf-8'))
            message = self.conn.recv(1024).decode('utf-8')
            command,size = message.split(' ')
            size = int(size)
            filesize = os.path.getsize(filepath)
            self.conn.sendall(bytes(str(filesize), 'utf-8'))
            if command == 'restart':
                if filesize < size:
                    print('文件大小异常')
                    return None
                message = self.conn.recv(1024).decode('utf-8')
                if message == 'completed':
                    print('文件已在服务端')
                    return None
                elif message == 'send':
                    sender = filesender(self.conn,filepath,size)
                    sender.start()
                    # while sender.is_alive():
                    #     if input('>>>') == 'pause':
                    #         order = 'pause'
            elif command == 'start':
                sender = filesender(self.conn, filepath, size)
                sender.start()
                # while sender.is_alive():
                #     if input('>>>') == 'pause':
                #         order = 'pause'
        else:
            print('目录里没有此文件')

    def download(self,args):
        filename, = args
        filepath = os.path.join(settings.download_path,filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            message = 'download' + ' ' + filename + ' ' + str(size)
        else:
            size = 0
            message = 'download' + ' ' + filename + ' ' + '0'
        self.conn.sendall(bytes(message, 'utf-8'))
        message = self.conn.recv(1024).decode('utf-8')
        filesize = int(message)
        if filesize == 0:
            print('服务端没有此文件')
            return None
        if size == filesize:
            self.conn.sendall(bytes('completed', 'utf-8'))
            print('文件已经完成')
        elif size < filesize:
            self.conn.sendall(bytes('start', 'utf-8'))
            recv = receiver(self.conn,filepath,filesize)
            recv.start()
        else:
            print('文件大小错误')

    def cd(self,args):
        message = 'cd' + ' ' + args[0]
        self.conn.sendall(bytes(message,'utf-8'))
        self.show_dirs()

    def ls(self):
        message = 'ls' + ' ' + '_'
        self.conn.sendall(bytes(message, 'utf-8'))
        self.show_dirs()

    def rm(self,args):
        message = 'rm' + ' ' + args[0]
        self.conn.sendall(bytes(message,'utf-8'))
        self.show_dirs()

    def quit(self):
        self.conn.close()
        sys.exit()

    def log_in(self):
        message = self.conn.recv(1024)
        print(message.decode('utf-8'))
        num = input('>>>')
        if num == '1':
            self.conn.sendall(bytes(num,'utf-8'))
            message = self.conn.recv(1024)
            print(message.decode('utf-8'),end='')
            usrname = input()
            self.conn.sendall(bytes(usrname,'utf-8'))
            message = self.conn.recv(1024)
            message = message.decode('utf-8')
            if message == 'no user':
                print('没有此用户')
                return False
            print(message,end='')
            passwd = input()
            self.conn.sendall(bytes(passwd,'utf-8'))
            message = self.conn.recv(1024)
            message = message.decode('utf-8')
            if message == 'passwd error':
                print('用户密码错误')
                return False
            print(message)
            return True
        elif num == '2':
            self.conn.sendall(bytes(num, 'utf-8'))
            message = self.conn.recv(1024)
            print(message.decode('utf-8'), end='')
            usrname = input()
            self.conn.sendall(bytes(usrname, 'utf-8'))
            message = self.conn.recv(1024)
            print(message.decode('utf-8'), end='')
            passwd = input()
            self.conn.sendall(bytes(passwd, 'utf-8'))
            message = self.conn.recv(1024)
            print(message.decode('utf-8'), end='')
            passwd = input()
            self.conn.sendall(bytes(passwd, 'utf-8'))

            message = self.conn.recv(1024)
            message = message.decode('utf-8')
            if message == 'passwd error':
                print('密码输入错误')
                return False
            print(message)
            return True

class filesender(threading.Thread):
    '''
    专门发送文件的线程
    '''
    def __init__(self,conn,filepath,size):
        super(filesender,self).__init__()
        self.conn = conn
        self.filepath = filepath
        self.size = size

    def run(self):
        with open(self.filepath, 'rb') as f:
            global order
            order = 'go on'
            f.seek(self.size)

            filesize = os.path.getsize(self.filepath)

            func = filesender.factary(time.time(),self.size)
            func(self.size,filesize)
            while filesize != self.size:
                data = f.read(1024)
                self.conn.sendall(data)
                self.size += len(data)
                message = self.conn.recv(2).decode('utf-8')
                if message != 'ok':
                    print('文件传输异常')
                    break
                if order == 'pause':
                    self.conn.sendall(bytes(order, 'utf-8'))
                    print('文件传输已暂停')
                    break
                if order not in ('go on','pause'):
                    self.conn.sendall(bytes('go on', 'utf-8'))
                else:
                    self.conn.sendall(bytes(order, 'utf-8'))
                func(self.size,filesize)
            else:
                print('文件传输完成')

    @staticmethod
    def factary(t,start_size):
        '''
        一个工厂函数，创建用于显示进度条和计算传输速度的函数
        :param t: 当前系统时间
        :param start_size: 开始文件大小
        :return: 返回一个函数
        '''
        start = t
        pre_size = start_size
        def fun(size,filesize):
            nonlocal start  # 使用闭包，用于保存函数运行状态
            nonlocal pre_size
            current = time.time()
            if (current - start) > 0.5:
                percent = int(round(size/filesize,2) * 100)
                hashes = '>' * int(percent/100.0 * 60)
                spaces = '-' * (60 - len(hashes))
                speed = round((size-pre_size)/(current-start),2)/1024
                sys.stdout.write("\rPercent: [%s] %d%%  %0.2f KB/s"%(hashes + spaces, percent,speed))
                sys.stdout.flush()
                start = current
                pre_size = size
        return fun

class receiver(threading.Thread):
    '''
    专门接收文件的线程
    '''
    def __init__(self,conn,filepath,filesize):
        super(receiver,self).__init__()
        self.conn = conn
        self.filepath = filepath
        self.filesize = filesize

    def run(self):
        with open(self.filepath,'ab') as f:
            global order
            order = 'go on'
            size = os.path.getsize(self.filepath)

            func = filesender.factary(time.time(),size)
            func(size, self.filesize)
            while size != self.filesize:
                data = self.conn.recv(1024)
                f.write(data)
                size += len(data)
                if order == 'pause':
                    self.conn.sendall(bytes('pause','utf-8'))
                    print('文件传输暂停')
                    break
                else:
                    self.conn.sendall(bytes('go on','utf-8'))
                func(size, self.filesize)
            else:
                print('文件传输完成')

def log_in(conn):
    '''
    处理用户登录的函数
    :param conn: 套接字
    :return: usr对象
    '''
    message = '''
    ----------- 欢迎进入 --------------
    1. 登录
    2. 注册
    -----------------------------------
    '''
    message = bytes(message,'utf-8')
    conn.sendall(message)
    data = conn.recv(1024)
    data = data.decode('utf-8')

    if data == '1':
        message = '请输入用户名：'
        message = bytes(message,'utf-8')
        conn.sendall(message)
        usrname = conn.recv(1024)
        usrname = usrname.decode('utf-8')

        usr_list = user.get_all_list()
        for i in usr_list:
            if i.name == usrname:
                usr_obj = i
                break
        else:
            message = 'no user'
            conn.sendall(bytes(message,'utf-8'))
            return None

        message = '请输入密码：'
        message = bytes(message, 'utf-8')
        conn.sendall(message)
        message = conn.recv(1024)
        passwd = message.decode('utf-8')
        if passwd == usr_obj.password:
            message = '登录成功\n'
            conn.sendall(bytes(message,'utf-8'))
            return usr_obj
        else:
            message = 'passwd error'
            conn.sendall(bytes(message,'utf-8'))
            return None

    if data == '2':
        message = '请输入注册用户名：'
        message = bytes(message, 'utf-8')
        conn.sendall(message)
        message = conn.recv(1024)
        usrname = message.decode('utf-8')

        message = '请输入密码：'
        message = bytes(message, 'utf-8')
        conn.sendall(message)
        message = conn.recv(1024)
        passwd = message.decode('utf-8')
        message = '请确认密码：'
        message = bytes(message, 'utf-8')
        conn.sendall(message)
        message = conn.recv(1024)
        _passwd = message.decode('utf-8')

        if passwd == _passwd:
            usr_obj = user(usrname,passwd)
            usr_obj.save()
            message = '用户注册成功\n'
            message = bytes(message, 'utf-8')
            conn.sendall(message)
            return usr_obj
        else:
            message = 'passwd error'
            message = bytes(message, 'utf-8')
            conn.sendall(message)
            return None
