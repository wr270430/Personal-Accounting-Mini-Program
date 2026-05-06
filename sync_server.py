"""
记账系统 - 多设备同步服务端
纯 Python 标准库，无需安装任何依赖。

启动: python sync_server.py
默认端口: 8520
数据文件: sync_data.json（自动创建）
"""

import json
import os
import sys
import time
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = int(os.environ.get('PORT') or os.environ.get('SYNC_PORT', 8520))
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data.json')
TOKEN = os.environ.get('SYNC_TOKEN', '')  # 可选：设置密码保护

# 跨设备同步数据存储
# 结构: { "device_id": { "data": [...], "memory": {...}, "updated_at": "ISO" } }
sync_store = {}


def load_store():
    global sync_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                sync_store = json.load(f)
            print(f'[OK] 已加载数据文件: {DATA_FILE} ({len(sync_store)} 个设备)')
        else:
            sync_store = {}
            print(f'[NEW] 创建数据文件: {DATA_FILE}')
    except Exception as e:
        print(f'[WARN] 加载数据失败: {e}，使用空数据')
        sync_store = {}


def save_store():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(sync_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[ERR] 保存数据失败: {e}')


def merge_data(device_id, incoming):
    """合并数据 - 按 ID 去重，保留最新版本"""
    if device_id not in sync_store:
        sync_store[device_id] = {'data': [], 'memory': {}, 'updated_at': '', 'device_name': ''}

    existing_map = {t['id']: t for t in sync_store[device_id]['data']}
    incoming_data = incoming.get('data', [])
    incoming_memory = incoming.get('memory', {})

    for t in incoming_data:
        tid = t.get('id')
        if tid in existing_map:
            # 保留时间戳更新的那条
            existing_time = existing_map[tid].get('createdAt', '')
            new_time = t.get('createdAt', '')
            if new_time >= existing_time:
                existing_map[tid] = t
        else:
            existing_map[tid] = t

    sync_store[device_id]['data'] = list(existing_map.values())
    sync_store[device_id]['data'].sort(key=lambda t: t.get('date', ''), reverse=True)

    # 合并记忆(memory)
    existing_memory = sync_store[device_id].get('memory', {})
    for key, val in incoming_memory.items():
        if key not in existing_memory or (val.get('lastUsed', '') >= existing_memory[key].get('lastUsed', '')):
            existing_memory[key] = val
        else:
            # 保留 count 更大的
            if val.get('count', 0) > existing_memory[key].get('count', 0):
                existing_memory[key]['count'] = val['count']
                existing_memory[key]['amounts'] = val.get('amounts', [])
    sync_store[device_id]['memory'] = existing_memory

    sync_store[device_id]['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    sync_store[device_id]['device_name'] = incoming.get('device_name', '未知设备')
    save_store()


def count_active(data_list):
    """Count records that are not soft-deleted"""
    return sum(1 for t in data_list if not t.get('_deleted'))


def get_all_data():
    """合并所有设备的数据返回（按 ID 去重，取最新）"""
    merged_map = {}
    merged_memory = {}

    for device_id, device_data in sync_store.items():
        for t in device_data.get('data', []):
            tid = t.get('id')
            if tid in merged_map:
                if t.get('createdAt', '') >= merged_map[tid].get('createdAt', ''):
                    merged_map[tid] = t
            else:
                merged_map[tid] = t

        for key, val in device_data.get('memory', {}).items():
            if key not in merged_memory or (val.get('lastUsed', '') >= merged_memory[key].get('lastUsed', '')):
                merged_memory[key] = val

    result_data = list(merged_map.values())
    result_data.sort(key=lambda t: t.get('date', ''), reverse=True)
    return {'data': result_data, 'memory': merged_memory}


class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f'[{time.strftime("%H:%M:%S")}] {self.client_address[0]} - {args[0]}')

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Sync-Token, X-Device-Id, X-Device-Name')
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self):
        if not TOKEN:
            return True
        token = self.headers.get('X-Sync-Token', '')
        return token == TOKEN

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Sync-Token, X-Device-Id, X-Device-Name')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # Serve web UI without auth
        if path == '/' or path == '/index.html':
            try:
                html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
                with open(html_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                body = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(body))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(body)
                return
            except FileNotFoundError:
                self._send_json({'error': 'index.html not found'}, 404)
                return

        if not self._check_auth():
            self._send_json({'error': 'Token error'}, 403)
            return

        if path == '/api/status':
            self._send_json({
                'status': 'ok',
                'devices': len(sync_store),
                'total_records': sum(count_active(d.get('data', [])) for d in sync_store.values()),
                'stored_since': time.strftime('%Y-%m-%d %H:%M:%S'),
                'version': '2.1'
            })

        elif path == '/api/data':
            device_id = self.headers.get('X-Device-Id', '')
            if device_id and device_id in sync_store:
                self._send_json({
                    'data': sync_store[device_id].get('data', []),
                    'memory': sync_store[device_id].get('memory', {}),
                    'updated_at': sync_store[device_id].get('updated_at', '')
                })
            else:
                self._send_json(get_all_data())

        elif path == '/api/all':
            self._send_json({
                'devices': sync_store,
                'merged': get_all_data()
            })

        elif path == '/api/devices':
            devices = {did: {'device_name': d.get('device_name', ''), 'records': count_active(d.get('data', [])), 'updated_at': d.get('updated_at', '')} for did, d in sync_store.items()}
            self._send_json({'devices': devices, 'count': len(devices)})

        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        if not self._check_auth():
            self._send_json({'error': 'Token 错误'}, 403)
            return

        path = urlparse(self.path).path

        if path == '/api/sync':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                incoming = json.loads(body)

                device_id = self.headers.get('X-Device-Id', 'unknown')
                if not device_id or device_id == 'unknown':
                    device_id = 'device_' + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

                merge_data(device_id, incoming)
                merged = get_all_data()

                self._send_json({
                    'ok': True,
                    'device_id': device_id,
                    'merged': merged,
                    'total_devices': len(sync_store)
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 400)

        elif path == '/api/device/delete':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                req = json.loads(body)
                target = req.get('device_id', '')
                if target and target in sync_store:
                    del sync_store[target]
                    save_store()
                    self._send_json({'ok': True, 'deleted': target, 'remaining': len(sync_store)})
                else:
                    self._send_json({'error': 'Device not found'}, 404)
            except Exception as e:
                self._send_json({'error': str(e)}, 400)

        else:
            self._send_json({'error': 'Not found'}, 404)


def main():
    load_store()

    # Handle Windows console encoding issues
    banner = f'''
+==========================================+
|  记账系统 - 多设备同步服务端              |
|                                          |
|   地址: http://0.0.0.0:{PORT}           |
|   本机: http://localhost:{PORT}          |
|   数据: {DATA_FILE}
|   {'密码: 已设置' if TOKEN else '密码: 未设置（开放访问）'}
|                                          |
|   API:                                   |
|   GET  /api/status  - 服务状态           |
|   GET  /api/data    - 获取数据           |
|   POST /api/sync    - 同步数据           |
|   GET  /api/devices - 设备列表           |
|                                          |
|   设置密码: set SYNC_TOKEN=你的密码       |
|   设置端口: set SYNC_PORT=8520            |
+==========================================+
'''
    try:
        print(banner)
    except UnicodeEncodeError:
        print(banner.encode('ascii', errors='replace').decode('ascii'))

    server = HTTPServer(('0.0.0.0', PORT), SyncHandler)
    print(f'服务已启动，按 Ctrl+C 停止...')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
        server.shutdown()


if __name__ == '__main__':
    main()
