#!/usr/bin/env.python
# _*_ coding:utf-8 _*_
# Author:Xuanzhe Lv

import asyncio, os, inspect, logging, functools

from urllib import parse
from aiohttp import web
from apis import APIError

def get(path):
    '''
    Define decorator @get('/path')
    :param path: 
    :return: 
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    :param path: 
    :return: 
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

#运用inspecg模块创建几个函数来用于获取URL处理函数与request参数之间的关系
def get_required_kw_args(fn): #获取没有默认值的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn): #获取命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn): #判断有没有命名关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_args(fn): #判断有没有关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_args(fn): #判断有没有'request'参数，且该参数是否为最后一个参数
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name,param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL
                      and param.kind != inspect.Parameter.KEYWORD_ONLY
                      and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s'%(fn.__name__,str(sig)))
    return found


#定义RequestHandler,正式向request参数获取URL处理函数所需的参数
class RequestHandler(object):
    def __init__(self,app,fn):#接受app参数
        self._app = app
        self._fn = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_named_kw_arg = has_named_kw_args(fn)
        self._has_var_kw_arg = has_var_kw_args(fn)
        self._has_request_arg = has_request_args(fn)

    async def __call__(self , request): #__call__这里要构造协程
        kw = None
        if self._has_named_kw_arg or self._has_var_kw_arg or self._required_kw_args:
            if request.method == 'POST': #判断客户端发来的方法是否为POST
                if not request.content_type: #查询有没提交数据的格式（EncType）
                    return web.HTTPBadRequest(text='Missing Content_Type.')#这里被廖大坑了，要有text
                ct = request.content_type.lower() #小写
                if ct.startswith('application/json'): #startswith
                    params = await request.json() #Read request body decoded as json.
                    if not isinstance(params,dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post() # reads POST parameters from request body.If method is not POST, PUT, PATCH, TRACE or DELETE or content_type is not empty or application/x-www-form-urlencoded or multipart/form-data returns empty multidict.
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content_Tpye: %s'%(request.content_type))
            if request.method == 'GET':
                qs = request.query_string #The query string in the URL
                if qs:
                    kw = dict()
                    for k,v in parse.parse_qs(qs,True).items(): #Parse a query string given as a string argument.Data are returned as a dictionary. The dictionary keys are the unique query variable names and the values are lists of values for each name.
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args: #当函数参数没有关键字参数时，移去request除命名关键字参数所有的参数信息
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k,v in request.match_info.items(): #检查命名关键参数
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        if self._required_kw_args: #假如命名关键字参数(没有附加默认值)，request没有提供相应的数值，报错
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s'%(name))
        logging.info('call with args: %s' % str(kw))

        try:
            r = await self._fn(**kw)
            return r
        except APIError as e: #APIError另外创建
            return dict(error=e.error, data=e.data, message=e.message)


#编写一个add_route函数，用来注册一个URL处理函数
def add_route(app,fn):
    method = getattr(fn,'__method__',None)
    path = getattr(fn,'__route__',None)
    if method is None or path is None:
        return ValueError('@get or @post not defined in %s.'%str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn): #判断是否为协程且生成器,不是使用isinstance
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)'%(method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method,path,RequestHandler(app,fn))

#直接导入文件，批量注册一个URL处理函数
def add_routes(app,module_name):
    n = module_name.rfind('.')
    if n == -1:
        mod = __import__(module_name,globals(),locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n],globals(),locals(),[name],0),name)#第一个参数为文件路径参数，不能掺夹函数名，类名
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod,attr)
        if callable(fn):
            method = getattr(fn,'__method__',None)
            path = getattr(fn,'__route__',None)
            if path and method: #这里要查询path以及method是否存在而不是等待add_route函数查询，因为那里错误就要报错了
                add_route(app,fn)

#添加静态文件夹的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')#输出当前文件夹中'static'的路径
    app.router.add_static('/static/',path)#prefix (str) – URL path prefix for handled static files
    logging.info('add static %s => %s'%('/static/',path))