import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from aibot_link.relay import Store, Relay, now

OWNER='testowner_0123456789abcdef0123456789abcdef'

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=Relay(('127.0.0.1',0),Store(Path(self.temp.name)/'state.sqlite3'),OWNER)
        self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.server_thread.start()
        self.root=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close();self.server_thread.join(timeout=5)
        self.server.store.db.close()
        self.temp.cleanup()
    def request(self,path,body=None,bearer=None,expected=200):
        headers={'Content-Type':'application/json'}
        if bearer:headers['Authorization']='Bearer '+bearer
        req=Request(self.root+path,data=json.dumps(body).encode() if body is not None else None,
                    method='POST' if body is not None else 'GET',headers=headers)
        try:
            with urlopen(req,timeout=5) as res:status=res.status;data=json.load(res)
        except HTTPError as e:status=e.code;data=json.load(e)
        self.assertEqual(expected,status,(status,data))
        return data
    def add_device(self,name='Windows',caps=('codex','dsh')):
        p=self.request('/api/v1/pair/request',{'name':name,'capabilities':list(caps),'projects':['football']},expected=201)
        self.assertEqual('pending',self.request('/api/v1/pair/complete',{'pair_id':p['pair_id'],'pair_secret':p['pair_secret']})['status'])
        self.request('/api/v1/pair/approve',{'code':p['code']},OWNER)
        d=self.request('/api/v1/pair/complete',{'pair_id':p['pair_id'],'pair_secret':p['pair_secret']})
        self.request('/api/v1/agent/heartbeat',{},d['device_token'])
        return p,d
    def test_pair_and_auth(self):
        self.request('/api/v1/state',expected=403)
        p,d=self.add_device()
        self.request('/api/v1/pair/complete',{'pair_id':p['pair_id'],'pair_secret':p['pair_secret']},expected=404)
        self.request('/api/v1/agent/heartbeat',{},'wrong',expected=403)
        s=self.request('/api/v1/state',bearer=OWNER)
        self.assertEqual(s['devices'][0]['id'],d['device_id'])
        self.assertTrue(s['devices'][0]['online'])
    def test_codex_flow_and_cancel(self):
        _,device=self.add_device()
        t=self.request('/api/v1/tasks',{'prompt':'run tests','project':'football','provider':'auto','device_id':'auto'},OWNER,201)
        self.assertEqual('queued',t['status'])
        assigned=self.request('/api/v1/agent/claim',{},device['device_token'])['task']
        self.assertEqual(t['id'],assigned['id'])
        self.request(f'/api/v1/agent/tasks/{t["id"]}/events',{'kind':'log','message':'starting test'},device['device_token'])
        ev=self.request(f'/api/v1/tasks/{t["id"]}/events',bearer=OWNER)['events']
        self.assertTrue(any(x['message']=='starting test' for x in ev))
        self.request(f'/api/v1/tasks/{t["id"]}/cancel',{},OWNER)
        control=self.request(f'/api/v1/agent/tasks/{t["id"]}/control',bearer=device['device_token'])
        self.assertTrue(control['cancel_requested'])
        final=self.request(f'/api/v1/agent/tasks/{t["id"]}/finish',{'status':'completed','summary':'done'},device['device_token'])
        self.assertEqual(final['status'],'cancelled')
        self.assertIsNone(self.request('/api/v1/agent/claim',{},device['device_token'])['task'])
    def test_dsh_approval(self):
        _,device=self.add_device()
        t=self.request('/api/v1/tasks',{'prompt':'make a change','project':'football','provider':'dsh'},OWNER,201)
        self.assertEqual('awaiting_approval',t['status'])
        self.assertIsNone(self.request('/api/v1/agent/claim',{},device['device_token'])['task'])
        self.request(f'/api/v1/tasks/{t["id"]}/approve',{},OWNER)
        self.assertEqual(t['id'],self.request('/api/v1/agent/claim',{},device['device_token'])['task']['id'])
        final=self.request(f'/api/v1/agent/tasks/{t["id"]}/finish',{'status':'completed','summary':'done'},device['device_token'])
        self.assertEqual('completed',final['status'])
    def test_permissions_project_validation_revoke(self):
        _,device=self.add_device()
        self.request('/api/v1/tasks',{'prompt':'ok','project':'other'},OWNER,404)
        self.request('/api/v1/tasks',{'prompt':'ok','project':'football'},'invalid',403)
        self.request(f'/api/v1/devices/{device["device_id"]}/revoke',{},OWNER)
        self.request('/api/v1/agent/heartbeat',{},device['device_token'],403)
    def test_mobile_assets(self):
        req=Request(self.root+'/')
        with urlopen(req,timeout=5) as response:
            self.assertIn('text/html',response.headers['Content-Type'])
            self.assertIn('Aibot Link',response.read().decode())
        with urlopen(self.root+'/mobile.js',timeout=5) as response:
            self.assertIn('javascript',response.headers['Content-Type'])
    def test_cross_device_handoff(self):
        _,first=self.add_device('Windows')
        _,second=self.add_device('Mac')
        t=self.request('/api/v1/tasks',{'prompt':'build website','project':'football','device_id':first['device_id']},OWNER,201)
        self.request('/api/v1/agent/claim',{},first['device_token'])
        self.request(f'/api/v1/agent/tasks/{t["id"]}/finish',{'status':'completed','summary':'Finished design; tests remain'},first['device_token'])
        onward=self.request('/api/v1/tasks',{'prompt':'continue tests','project':'football','device_id':second['device_id'], 'parent_task_id':t['id']},OWNER,201)
        self.assertEqual(onward['parent_task_id'],t['id'])
        self.assertIn('Finished design',onward['prompt'])
        self.assertEqual(onward['device_id'],second['device_id'])
    def test_revoked_running_cannot_finish(self):
        _,d=self.add_device('Windows')
        t=self.request('/api/v1/tasks',{'prompt':'hello','project':'football'},OWNER,201)
        self.request('/api/v1/agent/claim',{},d['device_token'])
        self.request(f'/api/v1/devices/{d["device_id"]}/revoke',{},OWNER)
        self.request(f'/api/v1/agent/tasks/{t["id"]}/finish',{'status':'completed'},d['device_token'],403)
        tasks=self.request('/api/v1/state',bearer=OWNER)['tasks']
        self.assertEqual('interrupted',next(x for x in tasks if x['id']==t['id'])['status'])
    def test_no_public_bind_required_by_runner(self):
        from aibot_link.bridge import safe_server
        self.assertEqual(safe_server('http://localhost:8787'), 'http://localhost:8787')
        with self.assertRaises(ValueError):safe_server('http://example.com:8787')

if __name__=='__main__':unittest.main()
