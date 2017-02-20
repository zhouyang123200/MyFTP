#!/usr/bin/python
# -*- coding: utf-8 -*-
# __author__: Administrator
# __date__  : 2016/10/8

from core import models
from conf import settings

def run():
    clt = models.client_soft(settings.address)
    clt.run()