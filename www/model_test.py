#!/usr/bin/env.python
# _*_ coding:utf-8 _*_
# Author:Xuanzhe Lv

import logging;logging.basicConfig(level=logging.INFO)
import orm
from model import User,Blog,Comment
import asyncio

async def test(loop):
    await orm.create_pool(user='www-data',password='www-data',db='awesome',loop=loop)
    u = User(name='Test2',email='test2@example.com',passwd='12345678',image='about:blank')
    await u.save()
    
loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
