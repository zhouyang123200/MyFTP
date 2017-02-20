#!/usr/bin/python
# -*- coding: utf-8 -*-
# __author__: Administrator
# __date__  : 2016/10/8

import socketserver
from core import models
from conf import settings

def run():
    server = socketserver.ThreadingTCPServer(settings.address,models.FTPServerHandler)
    server.serve_forever()
