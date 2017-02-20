#!/usr/bin/python3.5
# -*- coding: utf-8 -*-
# __author__: Administrator
# __date__  : 2016/10/8

import os
import sys
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(base_dir)
sys.path.append(base_dir)

from core import server_main

if __name__ == '__main__':
    server_main.run()
