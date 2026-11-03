"""Aibot Link V1.1 relay: owner-authenticated task router and device pairing.

No AI credentials are ever transmitted to this server. Bind localhost, serve via HTTPS proxy.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

MAX_JSON = 16_384
MAX_PROMPT = 4_000
PAIR_TTL = 600
HEARTBEAT_WINDOW = 75
STATUSES = {"queued", "awaiting_approval", "running", "completed", "failed", "cancelled", "interrupted"}

def now(): return int(time.time())
def digest(token: str): return hashlib.sha256(token.encode('utf-8')).hexdigest()
def token(): return secrets.token_urlsafe(32)

def validate_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must have 1-{limit} characters")
    return value.strip()

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS devices (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
          capabilities TEXT NOT NULL, projects TEXT NOT NULL,
          paired_at INTEGER NOT NULL, last_seen INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS pairings (
          id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, code_hash TEXT NOT NULL,
          name TEXT NOT NULL, capabilities TEXT NOT NULL, projects TEXT NOT NULL,
          expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          approved INTEGER NOT NULL DEFAULT 0, claimed INTEGER NOT NULL DEFAULT 0,
          device_id TEXT, device_token TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, prompt TEXT NOT NULL, provider TEXT NOT NULL,
          project TEXT NOT NULL, device_id TEXT NOT NULL,
          status TEXT NOT NULL, approval_reason TEXT, parent_task_id TEXT,
          created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
          cancel_requested INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
          at INTEGER NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_task_device ON tasks(device_id,status,created_at);
        CREATE INDEX IF NOT EXISTS idx_event_task ON events(task_id,seq);
        ''')
        if 'parent_task_id' not in [x[1] for x in self.db.execute('PRAGMA table_info(tasks)')]:
            self.db.execute('ALTER TABLE tasks ADD COLUMN parent_task_id TEXT')
    def rows(self, sql, params=()):
        return [dict(x) for x in self.db.execute(sql, params).fetchall()]
    def row(self, sql, params=()):
        x = self.db.execute(sql, params).fetchone()
        return dict(x) if x else None
    def execute(self, sql, params=()): return self.db.execute(sql, params)
    def public_device(self, d):
        return {k:d[k] for k in ("id","name","last_seen","paired_at")}|{
            "online":d["last_seen"]>=now()-HEARTBEAT_WINDOW and not d["revoked"],
            "capabilities":json.loads(d["capabilities"]),
            "projects":json.loads(d["projects"])}
    def public_task(self, t):
        return {k:t[k] for k in ("id","prompt","provider","project","device_id","status","approval_reason","created_at","updated_at","cancel_requested","summary","parent_task_id")}
    def reap_stale(self):
        # Never silently re-execute a crashed task; mark interrupted for owner handoff.
        old=self.rows("SELECT t.id FROM tasks t JOIN devices d ON t.device_id=d.id WHERE t.status='running' AND (d.last_seen<? OR d.revoked=1)",(now()-180,))
        for task in old:
            self.execute("UPDATE tasks SET status='interrupted',updated_at=? WHERE id=?",(now(),task['id']))
            self.add_event(task['id'],'status','Device disconnected; task interrupted, not automatically retried')
    def owner_state(self):
        with self.lock:
            self.reap_stale()
            devices=self.rows('SELECT * FROM devices WHERE revoked=0 ORDER BY last_seen DESC,name')
            tasks=self.rows('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50')
            return {"devices":[self.public_device(x) for x in devices],
                    "tasks":[self.public_task(x) for x in tasks], "server_time":now()}
    def pairing_start(self, body):
        name=validate_text(body.get('name'), 'device name', 72)
        capabilities=[c for c in body.get('capabilities', []) if c in ('codex','dsh')]
        if not isinstance(body.get('capabilities', []),list): raise ValueError('capabilities must be array')
        if not isinstance(body.get('projects',[]),list):raise ValueError('projects must be array')
        projects=[validate_text(x,'project name',80) for x in body.get('projects', [])]
        if len(projects)>30:raise ValueError('too many projects')
        ident=uuid.uuid4().hex; secret=token(); code=f'{secrets.randbelow(100_000_000):08d}'
        with self.lock:
            self.execute('DELETE FROM pairings WHERE expires_at<? OR claimed=1',(now(),))
            if self.row('SELECT COUNT(*) AS n FROM pairings')['n']>=25:raise ValueError('too many pending pair requests')
            self.execute('''INSERT INTO pairings(id,secret_hash,code_hash,name,capabilities,projects,expires_at)
                VALUES(?,?,?,?,?,?,?)''',(ident,digest(secret),digest(code),name,json.dumps(capabilities),json.dumps(projects),now()+PAIR_TTL))
        return {"pair_id":ident,"pair_secret":secret,"code":code,"expires_in":PAIR_TTL}
    def pairing_approve(self, code):
        if not isinstance(code,str) or len(code)!=8 or not code.isdigit():raise ValueError('invalid pairing code')
        with self.lock:
            pair=self.row('SELECT * FROM pairings WHERE code_hash=? AND expires_at>=? AND approved=0 AND claimed=0',(digest(code),now()))
            if not pair:raise LookupError('pairing expired or invalid')
            device_id=uuid.uuid4().hex; device_token=token()
            self.execute('''INSERT INTO devices(id,name,token_hash,capabilities,projects,paired_at)
                VALUES(?,?,?,?,?,?)''',(device_id,pair['name'],digest(device_token),pair['capabilities'],pair['projects'],now()))
            self.execute('UPDATE pairings SET approved=1, device_id=?,device_token=? WHERE id=?',(device_id,device_token,pair['id']))
            return {"device_id":device_id,"name":pair['name']}
    def pairing_complete(self, ident, secret):
        with self.lock:
            pair=self.row('SELECT * FROM pairings WHERE id=? AND expires_at>=?',(ident,now()))
            if not pair or not hmac.compare_digest(pair['secret_hash'],digest(secret)):raise PermissionError('invalid pairing secret')
            if pair['claimed']:raise LookupError('pairing already claimed')
            if not pair['approved']:return {"status":"pending"}
            self.execute('UPDATE pairings SET claimed=1,device_token=NULL WHERE id=?',(ident,))
            return {"status":"paired","device_id":pair['device_id'],"device_token":pair['device_token']}
    def auth_device(self, bearer):
        with self.lock:
            if not bearer:return None
            return self.row('SELECT * FROM devices WHERE token_hash=? AND revoked=0',(digest(bearer),))
    def owner_create_task(self, body):
        prompt=validate_text(body.get('prompt'),'prompt',MAX_PROMPT)
        project=validate_text(body.get('project'),'project',80)
        parent_task_id=body.get('parent_task_id')
        if parent_task_id is not None and (not isinstance(parent_task_id,str) or len(parent_task_id)!=32):
            raise ValueError('invalid handoff task id')
        provider=body.get('provider','auto'); wanted=body.get('device_id','auto')
        if provider not in ('auto','codex','dsh'):raise ValueError('invalid provider')
        with self.lock:
            if parent_task_id:
                previous=self.row('SELECT * FROM tasks WHERE id=?',(parent_task_id,))
                if not previous:raise LookupError('previous task not found')
                if previous['status'] in ('running','queued','awaiting_approval'):
                    raise ValueError('cancel or complete previous task before handing it off')
                if previous['project']!=project:raise ValueError('handoff project must match')
                prompt=('接续此前任务。此前任务：'+previous['prompt'][:800]+
                    '\n此前状态：'+previous['status']+'，交接摘要：'+previous['summary'][:1000]+
                    '\n当前指令：'+prompt)[:MAX_PROMPT]
            devices=[d for d in self.rows('SELECT * FROM devices WHERE revoked=0 ORDER BY last_seen DESC') if d['last_seen']>=now()-HEARTBEAT_WINDOW]
            if wanted != 'auto':devices=[d for d in devices if d['id']==wanted]
            eligible=[]
            for d in devices:
                caps=json.loads(d['capabilities']); projs=json.loads(d['projects'])
                if project not in projs:continue
                if provider=='auto':selected='codex' if 'codex' in caps else ('dsh' if 'dsh' in caps else None)
                else:selected=provider if provider in caps else None
                if selected:eligible.append((d,selected))
            if not eligible:raise LookupError('no online device offers this project/provider')
            # Automatic device choice prefers lower unfinished task count, then recent heartbeat.
            def load(item):
                d,_=item
                return self.row("SELECT count(*) AS n FROM tasks WHERE device_id=? AND status IN ('queued','running','awaiting_approval')",(d['id'],))['n']
            d,selected=min(eligible,key=load)
            status='awaiting_approval' if selected=='dsh' else 'queued'
            reason='DSH is not restricted by the Codex workspace sandbox. Explicit approval required.' if status=='awaiting_approval' else None
            ident=uuid.uuid4().hex
            self.execute('''INSERT INTO tasks(id,prompt,provider,project,device_id,status,approval_reason,parent_task_id,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(ident,prompt,selected,project,d['id'],status,reason,parent_task_id,now(),now()))
            self.add_event(ident,'status',f'Task {status}; assigned to {d["name"]} / {selected}')
            return self.public_task(self.row('SELECT * FROM tasks WHERE id=?',(ident,)))
    def add_event(self, task_id,kind,message):
        message=str(message)[:4000]
        self.execute('INSERT INTO events(task_id,at,kind,message) VALUES(?,?,?,?)',(task_id,now(),kind[:30],message))
    def task_owner_action(self,ident,action):
        with self.lock:
            t=self.row('SELECT * FROM tasks WHERE id=?',(ident,))
            if not t:raise LookupError('task not found')
            if action=='approve' and t['status']=='awaiting_approval':
                self.execute("UPDATE tasks SET status='queued',approval_reason=NULL,updated_at=? WHERE id=?",(now(),ident))
                self.add_event(ident,'approval','Owner approved this task')
            elif action=='cancel' and t['status'] in ('queued','awaiting_approval','running'):
                if t['status']=='running':
                    self.execute('UPDATE tasks SET cancel_requested=1,updated_at=? WHERE id=?',(now(),ident))
                else:self.execute("UPDATE tasks SET status='cancelled',cancel_requested=1,updated_at=? WHERE id=?",(now(),ident))
                self.add_event(ident,'status','Owner requested cancellation')
            else:raise ValueError('action not allowed in current state')
            return self.public_task(self.row('SELECT * FROM tasks WHERE id=?',(ident,)))
    def device_heartbeat(self,device):
        with self.lock:self.execute('UPDATE devices SET last_seen=? WHERE id=?',(now(),device['id']))
    def device_claim(self,device):
        with self.lock:
            self.device_heartbeat(device)
            if self.row("SELECT COUNT(*) AS n FROM tasks WHERE device_id=? AND status='running'",(device['id'],))['n']:
                return None
            t=self.row("SELECT * FROM tasks WHERE device_id=? AND status='queued' ORDER BY created_at,id LIMIT 1",(device['id'],))
            if not t:return None
            self.execute("UPDATE tasks SET status='running',updated_at=? WHERE id=? AND status='queued'",(now(),t['id']))
            self.add_event(t['id'],'status','Bridge started task')
            return self.public_task(self.row('SELECT * FROM tasks WHERE id=?',(t['id'],)))
    def device_task(self,device,ident):
        with self.lock:
            t=self.row('SELECT * FROM tasks WHERE id=? AND device_id=?',(ident,device['id']))
            if not t:raise LookupError('task not on this device')
            return t
    def device_event(self,device,ident,body):
        with self.lock:
            t=self.device_task(device,ident)
            if t['status']!='running':raise ValueError('task not running')
            self.add_event(ident,body.get('kind','log'),body.get('message',''))
            self.execute('UPDATE tasks SET updated_at=? WHERE id=?',(now(),ident))
    def device_finish(self,device,ident,body):
        status=body.get('status')
        if status not in ('completed','failed','cancelled','interrupted'):raise ValueError('invalid final status')
        summary=str(body.get('summary',''))[:4000]
        with self.lock:
            t=self.device_task(device,ident)
            if t['status']!='running':raise ValueError('task not running')
            if t['cancel_requested']:status='cancelled'
            self.execute('UPDATE tasks SET status=?,summary=?,updated_at=? WHERE id=?',(status,summary,now(),ident))
            self.add_event(ident,'status',f'Task {status}: {summary[:350]}')
            return self.public_task(self.row('SELECT * FROM tasks WHERE id=?',(ident,)))
    def events(self,ident,after):
        with self.lock:
            if not self.row('SELECT id FROM tasks WHERE id=?',(ident,)):raise LookupError('task not found')
            return self.rows('SELECT seq,at,kind,message FROM events WHERE task_id=? AND seq>? ORDER BY seq LIMIT 200',(ident,after))
    def revoke(self,ident):
        with self.lock:
            if not self.row('SELECT id FROM devices WHERE id=? AND revoked=0',(ident,)):raise LookupError('device not found')
            self.execute('UPDATE devices SET revoked=1 WHERE id=?',(ident,))
            self.execute("UPDATE tasks SET status='cancelled' WHERE device_id=? AND status IN ('queued','awaiting_approval')",(ident,))
            self.execute("UPDATE tasks SET status='interrupted',cancel_requested=1 WHERE device_id=? AND status='running'",(ident,))

class Relay(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,addr,store,owner_token):
        self.store=store
        self.owner_hash=digest(owner_token)
        super().__init__(addr,Handler)

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,fmt,*args):
        # No URL query strings, authorization headers, prompt contents, or pairing codes in logs.
        print(f'{self.address_string()} {self.command} {self.path.split("?")[0]}',flush=True)
    def send_json(self,status,obj):
        data=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(data)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n<0 or n>MAX_JSON:raise ValueError('request too large')
        body=self.rfile.read(n)
        obj=json.loads(body) if body else {}
        if not isinstance(obj,dict):raise ValueError('JSON object required')
        return obj
    def bearer(self):
        value=self.headers.get('Authorization','')
        return value[7:] if value.startswith('Bearer ') else ''
    def owner(self):
        return bool(self.bearer()) and hmac.compare_digest(digest(self.bearer()),self.server.owner_hash)
    def device(self):return self.server.store.auth_device(self.bearer())
    def require_owner(self):
        if not self.owner():raise PermissionError('owner authentication required')
    def require_device(self):
        d=self.device()
        if not d:raise PermissionError('device authentication required')
        return d
    def do_GET(self):self.route(False)
    def do_POST(self):self.route(True)
    def route(self,post):
        path=urlsplit(self.path).path
        try:
            if path in ('/','/index.html') and not post:return self.html()
            if path=='/mobile.js' and not post:return self.static_js()
            if path=='/health' and not post:return self.send_json(200,{'ok':True,'version':'1.1.0'})
            if path=='/api/v1/state' and not post:
                self.require_owner();return self.send_json(200,self.server.store.owner_state())
            if path=='/api/v1/pair/request' and post:
                return self.send_json(201,self.server.store.pairing_start(self.body()))
            if path=='/api/v1/pair/approve' and post:
                self.require_owner();return self.send_json(200,self.server.store.pairing_approve(self.body().get('code')))
            if path=='/api/v1/pair/complete' and post:
                body=self.body()
                return self.send_json(200,self.server.store.pairing_complete(body.get('pair_id'),body.get('pair_secret','')))
            if path=='/api/v1/tasks' and post:
                self.require_owner();return self.send_json(201,self.server.store.owner_create_task(self.body()))
            parts=path.strip('/').split('/')
            if len(parts)==5 and parts[:3]==['api','v1','tasks'] and parts[-1] in ('approve','cancel') and post:
                self.require_owner();return self.send_json(200,self.server.store.task_owner_action(parts[3],parts[-1]))
            if len(parts)==5 and parts[:3]==['api','v1','tasks'] and parts[-1]=='events' and not post:
                self.require_owner()
                after=max(0,int(parse_qs(urlsplit(self.path).query).get('after',['0'])[0]))
                return self.send_json(200,{'events':self.server.store.events(parts[3],after)})
            if len(parts)==5 and parts[:3]==['api','v1','devices'] and parts[-1]=='revoke' and post:
                self.require_owner();self.server.store.revoke(parts[3]);return self.send_json(200,{'ok':True})
            if path=='/api/v1/agent/claim' and post:
                d=self.require_device();return self.send_json(200,{'task':self.server.store.device_claim(d)})
            if path=='/api/v1/agent/heartbeat' and post:
                d=self.require_device();self.server.store.device_heartbeat(d);return self.send_json(200,{'ok':True})
            if len(parts)==6 and parts[:3]==['api','v1','agent'] and parts[3]=='tasks':
                d=self.require_device();ident=parts[4];action=parts[5]
                if action=='control' and not post:
                    t=self.server.store.device_task(d,ident)
                    return self.send_json(200,{'cancel_requested':bool(t['cancel_requested'])})
                if action=='events' and post:
                    self.server.store.device_event(d,ident,self.body());return self.send_json(200,{'ok':True})
                if action=='finish' and post:
                    return self.send_json(200,self.server.store.device_finish(d,ident,self.body()))
            return self.send_json(404,{'error':'not found'})
        except PermissionError as e:return self.send_json(403,{'error':str(e)})
        except LookupError as e:return self.send_json(404,{'error':str(e)})
        except (ValueError,TypeError,json.JSONDecodeError) as e:return self.send_json(400,{'error':str(e)})
        except Exception as e:
            print('Internal relay error:',type(e).__name__,flush=True)
            return self.send_json(500,{'error':'internal error'})
    def static_js(self):
        from importlib.resources import files
        content=files('aibot_link').joinpath('mobile.js').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','application/javascript; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(content)
    def html(self):
        from importlib.resources import files
        content=files('aibot_link').joinpath('mobile.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(content)

def main(argv=None):
    p=argparse.ArgumentParser(description='Aibot Link relay; place behind HTTPS reverse proxy')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=8787)
    p.add_argument('--db',default='./aibot-data/relay.sqlite3')
    args=p.parse_args(argv)
    owner=os.environ.get('AIBOT_OWNER_TOKEN','')
    if len(owner)<32:raise SystemExit('Set AIBOT_OWNER_TOKEN to a random secret of at least 32 chars (python -c "import secrets;print(secrets.token_urlsafe(32))")')
    if args.host not in ('127.0.0.1','::1','localhost') and not os.environ.get('AIBOT_I_UNDERSTAND_REVERSE_PROXY'):
        raise SystemExit('Refusing public bind without explicit opt-in; use Nginx HTTPS as frontend')
    store=Store(args.db)
    httpd=Relay((args.host,args.port),store,owner)
    print(f'Aibot Link relay ready: http://{args.host}:{args.port} (use HTTPS proxy for remote access)',flush=True)
    try:httpd.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:pass
    finally:httpd.server_close()
if __name__=='__main__':main()
