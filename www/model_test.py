#nd!/usr/bin/env.python
# _*_ coding:utf-8 _*_
# Author:Xuanzhe Lv

#import logging;logging.basicConfig(level=logging.INFO)
import orm
from model import User,Blog,Comment
import asyncio
import uuid
import time   

async def test(loop):
    await orm.create_pool(user='www-data',password='www-data',db='awesome',loop=loop)
    u = [User(name='Test4',email='%s@example.com'%uuid.uuid4().hex,passwd='12345678',image='about:blank') for x in range(1,10)]
    for y in u:
        await y.save()
    
loop = asyncio.get_event_loop()
start = time.clock()
#start = time.time()
loop.run_until_complete(test(loop))
#loop.run_until_complete(asyncio.wait(tasks))
end = time.clock()
#end = time.time()
print(end-start)
