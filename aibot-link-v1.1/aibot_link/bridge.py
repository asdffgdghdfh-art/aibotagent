"""Desktop Aibot Bridge for Windows/macOS/Linux.

Only Codex/DSH installed locally are invoked; tasks may run ONLY in configured workspaces.
No free-form shell command endpoint exists. No model credentials leave the computer.
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

DEFAULT_CONFIG=Path.home()/'.aibot-link'/'bridge.json'
MAX_EVENTS=120

def safe_server(raw):
    raw=raw.rstrip('/')
    u=urlsplit(raw)
    if u.scheme=='https' and u.netloc and not u.username and not u.password:return raw
    if u.scheme=='http' and u.hostname in ('localhost','127.0.0.1','::1'):return raw
    raise ValueError('Aibot Bridge requires HTTPS (except localhost testing)')

def http(server,path,body=None,bearer=None,timeout=15):
    server=safe_server(server)
    headers={'Content-Type':'application/json','Accept':'application/json'}
    if bearer:headers['Authorization']='Bearer '+bearer
    r=Request(server+path,headers=headers,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,method='POST' if body is not None else 'GET')
    try:
        with urlopen(r,timeout=timeout) as f:return json.load(f)
    except HTTPError as e:
        try:detail=json.loads(e.read())['error']
        except Exception:detail=str(e)
        if e.code in (401,403):raise PermissionError('relay: '+detail) from e
        raise RuntimeError('relay: '+detail) from e

def parse_projects(items):
    result={}
    for spec in items:
        if '=' not in spec:raise ValueError('project must be NAME=ABSOLUTE_DIRECTORY')
        name,path=spec.split('=',1)
        name=name.strip();p=Path(path).expanduser().resolve()
        if not name or len(name)>80 or not p.is_absolute() or not p.is_dir():
            raise ValueError(f'Invalid project workspace {spec!r}')
        if name in result:raise ValueError('Duplicate project name')
        result[name]=str(p)
    if not result:raise ValueError('At least one --project NAME=PATH is required')
    return result

def capabilities(enable_dsh=False):
    found=[]
    if shutil.which('codex'):found.append('codex')
    if enable_dsh and (shutil.which('dsh') or shutil.which('npx')):found.append('dsh')
    return found

def load_config(path):
    cfg=json.loads(Path(path).read_text(encoding='utf-8'))
    if cfg.get('version')!=1 or not cfg.get('device_token') or not cfg.get('projects'):
        raise ValueError('invalid Bridge configuration')
    cfg['server']=safe_server(cfg['server'])
    return cfg

def save_config(path,cfg):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise FileExistsError(f'{p} already exists; disconnect explicitly before re-pairing')
    with p.open('x',encoding='utf-8') as f:json.dump(cfg,f,ensure_ascii=False,indent=2)
    try:p.chmod(0o600)
    except OSError:pass

def pair(args):
    projects=parse_projects(args.project)
    caps=capabilities(args.enable_dsh)
    if not caps:raise SystemExit('Neither Codex nor enabled DSH was found; install and log in to a supported agent first')
    start=http(args.server,'/api/v1/pair/request',{'name':args.name,'capabilities':caps,'projects':list(projects)})
    print('\n'+'='*54+'\n  Aibot Link · 电脑配对\n'+'='*54)
    print('电脑名称:',args.name,'\n配对码:',start['code'])
    print('在手机 Aibot Link「我的设备」输入上面的 8 位配对码。')
    print('配对码 10 分钟后失效。')
    end=time.monotonic()+min(600,start.get('expires_in',600))
    while time.monotonic()<end:
        answer=http(args.server,'/api/v1/pair/complete',{'pair_id':start['pair_id'],'pair_secret':start['pair_secret']})
        if answer.get('status')=='paired':
            cfg={'version':1,'server':safe_server(args.server),'device_id':answer['device_id'],
                 'device_token':answer['device_token'],'name':args.name,'projects':projects,
                 'enable_dsh':bool(args.enable_dsh)}
            save_config(args.config,cfg)
            print('✅ 配对成功！设置已保存在',args.config)
            print('下一步执行: python -m aibot_link.bridge run')
            return
        time.sleep(4)
    raise SystemExit('配对超时；请重新执行 pair')

class DisplayState:
    def __init__(self,cfg):
        self.lock=threading.Lock()
        self.cfg=cfg
        self.status='等待任务'
        self.current=None
        self.events=deque(maxlen=MAX_EVENTS)
    def update(self,status=None,current=None):
        with self.lock:
            if status:self.status=status
            if current is not None:self.current=current
    def log(self,msg):
        text=str(msg)[:700]
        with self.lock:self.events.append({'at':time.strftime('%H:%M:%S'), 'text':text})
        print('[Aibot]',text,flush=True)
    def snapshot(self):
        with self.lock:return {'name':self.cfg['name'],'server':self.cfg['server'],
            'status':self.status,'task':self.current,'projects':list(self.cfg['projects']),
            'codex':bool(shutil.which('codex')),'dsh':bool(self.cfg.get('enable_dsh') and (shutil.which('dsh') or shutil.which('npx'))),
            'events':list(self.events)}

class LocalHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/state.json':
            data=json.dumps(self.server.display.snapshot(),ensure_ascii=False).encode()
            mime='application/json; charset=utf-8'
        elif self.path in ('/','/index.html'):
            from importlib.resources import files
            data=files('aibot_link').joinpath('desktop.html').read_bytes()
            mime='text/html; charset=utf-8'
        else:
            self.send_error(404);return
        self.send_response(200)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'")
        self.end_headers();self.wfile.write(data)

def start_local_ui(display,port):
    try:
        server=ThreadingHTTPServer(('127.0.0.1',port),LocalHandler)
        server.display=display
        threading.Thread(target=server.serve_forever,daemon=True).start()
        display.log(f'电脑控制面板 http://127.0.0.1:{port}')
    except OSError as e:display.log('控制面板不可用: '+str(e))

def codex_command(project,prompt):
    # No dangerous bypass flag. Codex can modify the configured workspace, not unrestricted OS paths.
    return ['codex','--sandbox','workspace-write','--ask-for-approval','never',
            'exec','--json','--cd',project,prompt]

def dsh_command(prompt):
    executable=shutil.which('dsh')
    if executable:return [executable,'--profile','headless','--json',prompt]
    return ['npx','--yes','@deepseek-ai/dsh','--profile','headless','--json',prompt]

def extract_event(line):
    try:
        item=json.loads(line)
        if isinstance(item,dict):
            if item.get('type') in ('item.completed','turn.completed','turn.failed'):
                return json.dumps(item,ensure_ascii=False)[:2300]
            if item.get('type') in ('item.started','turn.started'):return item['type']
            return ''
    except (ValueError,TypeError):pass
    return line[:2000]

def execute_task(cfg,t,display):
    task_id=t['id'];project_name=t['project'];project=cfg['projects'].get(project_name)
    if not project or not Path(project).resolve().is_dir():
        return 'failed','项目目录未获授权或不存在'
    provider=t['provider']
    if provider=='codex' and shutil.which('codex'):
        command=codex_command(project,t['prompt'])
    elif provider=='dsh' and cfg.get('enable_dsh'):
        # Owner approval was required by relay before task could become queued.
        command=dsh_command(t['prompt'])
    else:return 'failed','未检测到受支持的本机 Agent'
    display.log(f'{provider} 开始：{project_name}')
    try:
        proc=subprocess.Popen(command,cwd=project,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',errors='replace',bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0,
            start_new_session=(os.name!='nt'))
    except (OSError,ValueError) as e:return 'failed','启动失败：'+str(e)
    cancelled=threading.Event();done=threading.Event()
    def monitor():
        while not done.wait(4):
            try:
                response=http(cfg['server'],f'/api/v1/agent/tasks/{task_id}/control',bearer=cfg['device_token'])
                http(cfg['server'],'/api/v1/agent/heartbeat',{},cfg['device_token'])
                if response.get('cancel_requested'):
                    cancelled.set(); display.log('收到取消请求，停止 Agent')
                    proc.terminate();return
            except PermissionError:
                cancelled.set();display.log('设备权限已被撤销，停止执行')
                proc.terminate();return
            except (URLError,RuntimeError):pass
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    recent=deque(maxlen=16);last_event=0;sent=0
    try:
        for line in proc.stdout:
            cleaned=extract_event(line.strip())
            if not cleaned:continue
            recent.append(cleaned);display.log(cleaned[:150]);sent+=1
            if sent<=600:
                try:http(cfg['server'],f'/api/v1/agent/tasks/{task_id}/events',{'kind':'log','message':cleaned[:2000]},cfg['device_token'])
                except (URLError,RuntimeError):pass
        result=proc.wait(timeout=20)
        if cancelled.is_set():return 'cancelled','已按手机端请求取消'
        return ('completed' if result==0 else 'failed'),('执行完成' if result==0 else f'执行失败，退出码 {result}')+'；'+(' | '.join(recent)[-1500:])
    finally:
        done.set()
        if proc.poll() is None:proc.terminate()

def run(args):
    cfg=load_config(args.config)
    display=DisplayState(cfg)
    start_local_ui(display,args.ui_port)
    print(f'✅ Aibot Bridge 在线：{cfg["name"]}；授权项目：{", ".join(cfg["projects"])}')
    print(f'打开电脑控制面板 http://127.0.0.1:{args.ui_port}；Ctrl+C 结束。')
    while True:
        try:
            r=http(cfg['server'],'/api/v1/agent/claim',{},cfg['device_token'])
            t=r.get('task')
            if t:
                display.update(f'执行中：{t["project"]}',t['id'])
                status,summary=execute_task(cfg,t,display)
                try:http(cfg['server'],f'/api/v1/agent/tasks/{t["id"]}/finish',{'status':status,'summary':summary},cfg['device_token'])
                except RuntimeError as e:display.log('任务完成回执失败：'+str(e))
                display.update('等待任务','')
                display.log(f'{t["id"][:8]} {status}: {summary[:150]}')
            time.sleep(max(2,args.poll_interval))
        except KeyboardInterrupt:
            display.log('Bridge 正常退出');return
        except PermissionError as e:
            display.log('设备授权已失效，Bridge 停止运行：'+str(e));return
        except (URLError,RuntimeError,ValueError) as e:
            display.update('连接中断，自动重试','')
            display.log('网络或 Relay 错误：'+str(e));time.sleep(8)

def main(argv=None):
    parser=argparse.ArgumentParser(description='Aibot Link desktop bridge')
    parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    sub=parser.add_subparsers(dest='action',required=True)
    setup=sub.add_parser('pair',help='Pair this computer with phone using an 8-digit code')
    setup.add_argument('--server',required=True)
    setup.add_argument('--name',default=platform.node() or 'My Computer')
    setup.add_argument('--project',action='append',default=[],help='NAME=FULL_PATH; can repeat')
    setup.add_argument('--enable-dsh',action='store_true',help='Enable unsandboxed DSH tasks ONLY after explicit owner approval')
    worker=sub.add_parser('run',help='Run Bridge and local desktop control panel')
    worker.add_argument('--poll-interval',type=float,default=4.0)
    worker.add_argument('--ui-port',type=int,default=8766)
    sub.add_parser('status',help='Show configured projects and installed agents')
    args=parser.parse_args(argv)
    if args.action=='pair':pair(args)
    elif args.action=='run':run(args)
    elif args.action=='status':
        cfg=load_config(args.config)
        print(json.dumps({'device':cfg['name'],'server':cfg['server'],'projects':cfg['projects'],
            'detected_agents':capabilities(cfg['enable_dsh'])},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
