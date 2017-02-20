#!/usr/bin/python
# -*- coding: utf-8 -*-
# __author__: Administrator
# __date__  : 2016/10/8

import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_LEVEL = logging.INFO
address = ('192.168.1.104',9000)

download_path = os.path.join(BASE_DIR,'db','download')  # 客户端下载目录

LOG_TYPES = {
    'handler_logger': '服务器处理请求日志.log',
}

usr_data_path = os.path.join(BASE_DIR,'db','usr_data')  # 存放用户实例的目录
usr_filedata_path = os.path.join(BASE_DIR,'db','usrfiledata')   # 存放用户数据的目录
