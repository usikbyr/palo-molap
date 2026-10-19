#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import hashlib

PALO_URL = __import__("os").environ.get("PALO_URL", "http://127.0.0.1:7777")
PORT = 8080

def get_palo_session():
    pwd_md5 = hashlib.md5("admin".encode('utf-8')).hexdigest()
    req = urllib.request.urlopen(f"{PALO_URL}/server/login?user=admin&password={pwd_md5}")
    return req.read().decode('utf-8').split(";")[0]

class PaloViewerHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length) if length > 0 else b'{}'
        data = json.loads(body.decode('utf-8'))
        
        # 1. Mise à jour de cellule (avec support SPLASH)
        if parsed.path == "/api/cell/update":
            db_id = data.get("database")
            cube_id = data.get("cube")
            path = data.get("path")
            value = data.get("value")
            splash_mode = data.get("splash", 1) # 1=proportionnel par défaut
            
            try:
                sid = get_palo_session()
                params = urllib.parse.urlencode({
                    "sid": sid,
                    "database": db_id,
                    "cube": cube_id,
                    "path": path,
                    "value": value,
                    "splash": splash_mode
                })
                req = urllib.request.urlopen(f"{PALO_URL}/cell/replace?{params}")
                res = req.read().decode('utf-8')
                
                # Persistance
                urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={db_id}")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "res": res}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        # 2. Ajout d'élément dans une dimension (Base ou Consolidé)
        elif parsed.path == "/api/element/create":
            db_id = data.get("database")
            dim_id = data.get("dimension")
            elem_name = data.get("name")
            elem_type = data.get("type", 1) # 1=numérique, 4=consolidé
            children = data.get("children", "") # ex: "0,1,2"
            
            try:
                sid = get_palo_session()
                params = {
                    "sid": sid,
                    "database": db_id,
                    "dimension": dim_id,
                    "new_name": elem_name,
                    "type": elem_type
                }
                if elem_type == 4 and children:
                    params["children"] = children
                    
                req = urllib.request.urlopen(f"{PALO_URL}/element/create?{urllib.parse.urlencode(params)}")
                res = req.read().decode('utf-8')
                
                urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={db_id}")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "res": res}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        # 3. Suppression d'élément dans une dimension
        elif parsed.path == "/api/element/delete":
            db_id = data.get("database")
            dim_id = data.get("dimension")
            elem_id = data.get("element")
            
            try:
                sid = get_palo_session()
                params = urllib.parse.urlencode({
                    "sid": sid,
                    "database": db_id,
                    "dimension": dim_id,
                    "element": elem_id
                })
                req = urllib.request.urlopen(f"{PALO_URL}/element/destroy?{params}")
                res = req.read().decode('utf-8')
                
                urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={db_id}")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "res": res}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        # --- Creation : base / dimension / cube ---
        elif parsed.path in ("/api/db/create", "/api/dim/create", "/api/cube/create"):
            try:
                sid = get_palo_session()
                q = lambda v: urllib.parse.quote(str(v).strip(), safe="")
                name = data.get("name", "").strip()
                if not name:
                    raise ValueError("name is required")
                db = str(data.get("database", "")).strip()

                if parsed.path == "/api/db/create":
                    res = urllib.request.urlopen(
                        f"{PALO_URL}/database/create?sid={sid}&new_name={q(name)}").read().decode().strip()
                    new_id = res.split(";")[0]
                    urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={new_id}").read()

                elif parsed.path == "/api/dim/create":
                    if not db:
                        raise ValueError("database is required")
                    res = urllib.request.urlopen(
                        f"{PALO_URL}/dimension/create?sid={sid}&database={db}&new_name={q(name)}").read().decode().strip()
                    new_id = res.split(";")[0]
                    urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={db}").read()

                else:  # /api/cube/create
                    if not db:
                        raise ValueError("database is required")
                    dims = data.get("dimensions") or []
                    dims = [str(d).strip() for d in dims if str(d).strip()]
                    if not dims:
                        raise ValueError("at least one dimension is required")
                    res = urllib.request.urlopen(
                        f"{PALO_URL}/cube/create?sid={sid}&database={db}&new_name={q(name)}&dimensions={','.join(dims)}"
                    ).read().decode().strip()
                    new_id = res.split(";")[0]
                    urllib.request.urlopen(f"{PALO_URL}/database/save?sid={sid}&database={db}").read()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "id": new_id, "res": res}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        super().do_POST()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            try:
                sid = get_palo_session()
                dbs_raw = urllib.request.urlopen(f"{PALO_URL}/server/databases?sid={sid}").read().decode('utf-8')
                dbs = []
                for line in dbs_raw.strip().splitlines():
                    if line:
                        parts = line.split(";")
                        dbs.append({"id": parts[0], "name": parts[1].strip('"')})
                
                query = urllib.parse.parse_qs(parsed.query)
                target_db_id = query.get("db", [None])[0]
                
                target_db = None
                if target_db_id:
                    for d in dbs:
                        if d["id"] == target_db_id:
                            target_db = d
                            break
                if not target_db and dbs:
                    target_db = dbs[-1]
                
                result = {"databases": dbs, "selected_db": target_db, "cubes": [], "all_dimensions": []}
                
                if target_db:
                    db_id = target_db["id"]
                    
                    # Récupérer toutes les dimensions
                    dims_raw = urllib.request.urlopen(f"{PALO_URL}/database/dimensions?sid={sid}&database={db_id}").read().decode('utf-8')
                    for dline in dims_raw.strip().splitlines():
                        if not dline: continue
                        dparts = dline.split(";")
                        did = dparts[0]
                        dname = dparts[1].strip('"')
                        if dname.startswith("#_"): continue
                        
                        elems_raw = urllib.request.urlopen(f"{PALO_URL}/dimension/elements?sid={sid}&database={db_id}&dimension={did}").read().decode('utf-8')
                        elems = []
                        for eline in elems_raw.strip().splitlines():
                            if not eline: continue
                            eparts = eline.split(";")
                            elems.append({
                                "id": eparts[0],
                                "name": eparts[1].strip('"'),
                                "type": int(eparts[6]) if len(eparts) > 6 else 1 # 1=numeric, 4=consolidated
                            })
                        
                        result["all_dimensions"].append({
                            "id": did,
                            "name": dname,
                            "elements": elems
                        })
                    
                    # Lister les cubes
                    cubes_raw = urllib.request.urlopen(f"{PALO_URL}/database/cubes?sid={sid}&database={db_id}").read().decode('utf-8')
                    for cline in cubes_raw.strip().splitlines():
                        if not cline: continue
                        cparts = cline.split(";")
                        c_id = cparts[0]
                        c_name = cparts[1].strip('"')
                        dim_ids_str = cparts[3] if len(cparts) > 3 else ""
                        dim_ids = [d.strip() for d in dim_ids_str.split(",") if d.strip()]
                        
                        dimensions = []
                        for dim_id in dim_ids:
                            dim_match = next((d for d in result["all_dimensions"] if d["id"] == dim_id), None)
                            if dim_match:
                                dimensions.append(dim_match)
                            else:
                                dim_info = urllib.request.urlopen(f"{PALO_URL}/dimension/info?sid={sid}&database={db_id}&dimension={dim_id}").read().decode('utf-8')
                                dim_name = dim_info.split(";")[1].strip('"')
                                elems_raw = urllib.request.urlopen(f"{PALO_URL}/dimension/elements?sid={sid}&database={db_id}&dimension={dim_id}").read().decode('utf-8')
                                elems = []
                                for eline in elems_raw.strip().splitlines():
                                    if not eline: continue
                                    eparts = eline.split(";")
                                    elems.append({"id": eparts[0], "name": eparts[1].strip('"'), "type": int(eparts[6]) if len(eparts) > 6 else 1})
                                dimensions.append({"id": dim_id, "name": dim_name, "elements": elems})
                        
                        # Matrice de cellules
                        matrix = {}
                        if len(dimensions) == 2:
                            for row_elem in dimensions[0]["elements"]:
                                matrix[row_elem["name"]] = {}
                                for col_elem in dimensions[1]["elements"]:
                                    path = f"{row_elem['id']},{col_elem['id']}"
                                    val_raw = urllib.request.urlopen(f"{PALO_URL}/cell/value?sid={sid}&database={db_id}&cube={c_id}&path={path}").read().decode('utf-8')
                                    val_parts = val_raw.split(";")
                                    val = val_parts[2] if len(val_parts) > 2 else "0"
                                    is_consolidated = (row_elem["type"] == 4 or col_elem["type"] == 4)
                                    try:
                                        matrix[row_elem["name"]][col_elem["name"]] = {
                                            "value": float(val),
                                            "path": path,
                                            "is_consolidated": is_consolidated
                                        }
                                    except:
                                        matrix[row_elem["name"]][col_elem["name"]] = {
                                            "value": val,
                                            "path": path,
                                            "is_consolidated": is_consolidated
                                        }
                        
                        result["cubes"].append({
                            "id": c_id,
                            "name": c_name,
                            "dimensions": dimensions,
                            "matrix": matrix
                        })
                
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
            
        elif parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qonso Molap Studio - Splashing</title>
    <style>
        :root {
            --bg: #090d16; --panel: #131c2e; --ink: #f8fafc; --muted: #94a3b8;
            --line: #23324d; --violet: #a855f7; --violet-bg: #3b0764; --violet-ink: #e9d5ff;
            --primary: #38bdf8; --ok: #34d399;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0; background: var(--bg); color: var(--ink); font-size: 15px; line-height: 1.5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 0 0 40px;
        }
        .container { max-width: 1060px; margin: 0 auto; padding: 34px 20px 64px; }
        header {
            display: flex; justify-content: space-between; align-items: flex-end; gap: 16px;
            padding-bottom: 16px; border-bottom: 1px solid var(--line); margin-bottom: 20px;
        }
        h1 { font-size: 22px; margin: 0; font-weight: 700; letter-spacing: -0.01em; color: var(--primary); }
        h2 { font-size: 15px; margin: 0 0 4px; font-weight: 700; color: var(--ink); }
        .meta { color: var(--muted); font-size: 13px; }
        .card {
            background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
            padding: 18px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.35);
        }
        .controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; }
        select, input[type=text] {
            font: inherit; font-size: 14px; padding: 7px 10px; border: 1px solid var(--line);
            border-radius: 8px; background: #0b1322; color: var(--ink);
        }
        select:focus, input[type=text]:focus { outline: 2px solid rgba(56,189,248,0.45); outline-offset: 1px; }
        .btn {
            font: inherit; font-size: 14px; padding: 7px 14px; border: none;
            background: var(--primary); color: #0f172a; border-radius: 8px; cursor: pointer; font-weight: 600;
        }
        .btn:hover { opacity: 0.9; }
        .badge {
            font-size: 12px; color: var(--ok); background: #064e3b; border: 1px solid #065f46;
            border-radius: 999px; padding: 3px 10px; white-space: nowrap;
        }
        details.card summary { cursor: pointer; font-weight: 600; font-size: 15px; color: var(--ink); }
        table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 14px; }
        th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; }
        th {
            font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        th:first-child, td:first-child { text-align: left; }
        tbody tr:hover { background: #0f1829; }
        .editable { cursor: pointer; }
        .editable:hover { background: #1d2c47; }
        .consolidated, .consolidated-row td { background: var(--violet-bg); color: var(--violet-ink); font-weight: 700; }
        .consolidated:hover { background: #4c1d95 !important; }
        .dim-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; margin-top: 14px; }
        .dim-card { background: #0b1322; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
        .dim-title { display: flex; justify-content: space-between; gap: 8px; font-weight: 700; font-size: 14px; margin-bottom: 10px; color: var(--primary); }
        .elem-list { display: flex; flex-wrap: wrap; gap: 6px; min-height: 26px; }
        .elem-chip {
            font-size: 13px; background: #1e293b; border: 1px solid var(--line); border-radius: 999px;
            padding: 3px 10px; display: inline-flex; align-items: center; gap: 6px;
        }
        .consolidated-chip { background: var(--violet-bg); border-color: #7e22ce; color: var(--violet-ink); font-weight: 600; }
        .del-btn { cursor: pointer; color: var(--muted); font-size: 13px; font-weight: 700; }
        .del-btn:hover { color: #ef4444; }
        .add-form { display: flex; gap: 8px; margin-top: 10px; }
        #toast {
            display: none; position: fixed; right: 24px; bottom: 24px;
            background: #10b981; color: #022c22; font-weight: 600;
            padding: 10px 18px; border-radius: 8px;
            font-size: 14px; z-index: 50; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        .legend { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12.5px; color: var(--muted); margin-top: 10px; }
        .legend-box { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: middle; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Qonso Molap Studio</h1>
                <div class="meta">Edit any cell &middot; consolidated totals spill down to their children</div>
            </div>
            <span class="badge">&#9679; Connected</span>
        </header>

        <div class="controls">
            <label class="meta" for="dbSelect">Database</label>
            <select id="dbSelect" onchange="loadData(this.value)"></select>
            <button class="btn" onclick="loadData(currentDbId)">Refresh</button>
        </div>

        <details class="card">
            <summary>Setup &mdash; create a database, a dimension or a cube</summary>
            <div style="display: grid; gap: 12px; margin-top: 14px;">
                <div class="add-form" style="margin: 0;">
                    <input type="text" id="newDbName" placeholder="New database name..." style="flex: 1;"
                           onkeydown="if(event.key==='Enter') createDatabase()">
                    <button class="btn" onclick="createDatabase()">Create database</button>
                </div>
                <div class="add-form" style="margin: 0;">
                    <input type="text" id="newDimName" placeholder="New dimension name..." style="flex: 1;"
                           onkeydown="if(event.key==='Enter') createDimension()">
                    <button class="btn" onclick="createDimension()">Add dimension</button>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <input type="text" id="newCubeName" placeholder="New cube name..." style="flex: 1; min-width: 200px;"
                           onkeydown="if(event.key==='Enter') createCube()">
                    <div id="dimPick" style="display: flex; gap: 14px; flex-wrap: wrap;"></div>
                    <button class="btn" onclick="createCube()">Create cube</button>
                </div>
            </div>
        </details>

        <div id="cubeContent" class="meta">Loading...</div>

        <div class="card">
            <h2>Dimensions</h2>
            <div class="meta">Purple elements are consolidated roll-ups. Add a new element with the field below each dimension.</div>
            <div id="dimContent" class="dim-container"></div>
        </div>
    </div>

    <div id="toast">Operation succeeded!</div>

    <script>
        let currentDbId = null;

        async function postJSON(url, body) {
            try {
                const res = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
                return await res.json();
            } catch (e) {
                return {success: false, error: e.message};
            }
        }

        async function createDatabase() {
            const el = document.getElementById('newDbName');
            const name = el.value.trim();
            if (!name) return alert('Enter a database name.');
            const r = await postJSON('/api/db/create', {name: name});
            if (r.success) { el.value = ''; showToast(`Database "${name}" created`); loadData(r.id); }
            else alert('Error: ' + r.error);
        }

        async function createDimension() {
            const el = document.getElementById('newDimName');
            const name = el.value.trim();
            if (!name) return alert('Enter a dimension name.');
            if (!currentDbId) return alert('Create or select a database first.');
            const r = await postJSON('/api/dim/create', {database: currentDbId, name: name});
            if (r.success) { el.value = ''; showToast(`Dimension "${name}" created`); loadData(currentDbId); }
            else alert('Error: ' + r.error);
        }

        async function createCube() {
            const el = document.getElementById('newCubeName');
            const name = el.value.trim();
            if (!name) return alert('Enter a cube name.');
            if (!currentDbId) return alert('Create or select a database first.');
            const dims = Array.from(document.querySelectorAll('#dimPick input:checked')).map(i => i.value);
            if (!dims.length) return alert('Tick at least one dimension.');
            const r = await postJSON('/api/cube/create', {database: currentDbId, name: name, dimensions: dims});
            if (r.success) { el.value = ''; showToast(`Cube "${name}" created`); loadData(currentDbId); }
            else alert('Error: ' + r.error);
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        async function editCell(td, dbId, cubeId, path, oldVal, isConsolidated) {
            if (td.querySelector('input')) return;
            const input = document.createElement('input');
            input.type = 'number';
            input.step = 'any';
            input.value = oldVal;
            td.textContent = '';
            td.appendChild(input);
            input.focus();
            input.select();

            async function save() {
                const newVal = parseFloat(input.value);
                if (isNaN(newVal) || newVal === oldVal) {
                    td.textContent = oldVal.toLocaleString('fr-FR', {minimumFractionDigits: 1}) + ' €';
                    return;
                }
                td.textContent = '...';
                try {
                    const res = await fetch('/api/cell/update', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            database: dbId,
                            cube: cubeId,
                            path: path,
                            value: newVal,
                            splash: 1 // Splashing proportionnel activé
                        })
                    });
                    const r = await res.json();
                    if (r.success) {
                        if (isConsolidated) {
                            showToast(`🌊 Splashing applied: ${newVal.toLocaleString('en-US')} € spread across children!`);
                        } else {
                            showToast(`Cell updated: ${newVal.toLocaleString('en-US')} €`);
                        }
                        loadData(currentDbId);
                    } else {
                        alert('Error: ' + r.error);
                        td.textContent = oldVal.toLocaleString('fr-FR', {minimumFractionDigits: 1}) + ' €';
                    }
                } catch(e) {
                    alert('Network error: ' + e.message);
                    td.textContent = oldVal.toLocaleString('fr-FR', {minimumFractionDigits: 1}) + ' €';
                }
            }

            input.addEventListener('blur', save);
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') input.blur();
                if (e.key === 'Escape') {
                    input.removeEventListener('blur', save);
                    td.textContent = oldVal.toLocaleString('fr-FR', {minimumFractionDigits: 1}) + ' €';
                }
            });
        }

        async function addElement(dimId, inputId) {
            const input = document.getElementById(inputId);
            const name = input.value.trim();
            if (!name) return;

            try {
                const res = await fetch('/api/element/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ database: currentDbId, dimension: dimId, name: name })
                });
                const r = await res.json();
                if (r.success) {
                    showToast(`Element "${name}" added successfully`);
                    input.value = '';
                    loadData(currentDbId);
                } else {
                    alert('Error: ' + r.error);
                }
            } catch(e) {
                alert('Network error: ' + e.message);
            }
        }

        async function deleteElement(dimId, elemId, name) {
            if (!confirm(`Delete element "${name}" from this dimension?`)) return;

            try {
                const res = await fetch('/api/element/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ database: currentDbId, dimension: dimId, element: elemId })
                });
                const r = await res.json();
                if (r.success) {
                    showToast(`Element "${name}" deleted`);
                    loadData(currentDbId);
                } else {
                    alert('Error: ' + r.error);
                }
            } catch(e) {
                alert('Network error: ' + e.message);
            }
        }

        async function loadData(selectedDb = null) {
            const cubeContainer = document.getElementById('cubeContent');
            const dimContainer = document.getElementById('dimContent');
            try {
                const url = selectedDb ? `/api/data?db=${selectedDb}` : '/api/data';
                const res = await fetch(url);
                const data = await res.json();
                
                if (data.error) {
                    cubeContainer.innerHTML = `<div class="card" style="color: #f87171;">Error: ${data.error}</div>`;
                    return;
                }

                currentDbId = data.selected_db?.id;

                // Select des bases
                const select = document.getElementById('dbSelect');
                select.innerHTML = '';
                data.databases.forEach(db => {
                    const opt = document.createElement('option');
                    opt.value = db.id;
                    opt.textContent = `${db.name} (ID: ${db.id})`;
                    if (data.selected_db && db.id === data.selected_db.id) opt.selected = true;
                    select.appendChild(opt);
                });

                // Rendu des Dimensions
                let dimHtml = '';
                data.all_dimensions.forEach(d => {
                    const inputId = `new_elem_${d.id}`;
                    dimHtml += `
                        <div class="dim-card">
                            <div class="dim-title">
                                <span>📁 ${d.name}</span>
                                <span style="font-size: 12px; color: var(--muted);">${d.elements.length} elements</span>
                            </div>
                            <div class="elem-list">
                                ${d.elements.map(e => `
                                    <span class="elem-chip ${e.type === 4 ? 'consolidated-chip' : ''}">
                                        ${e.type === 4 ? '∑ ' : ''}${e.name}
                                        <span class="del-btn" onclick="deleteElement('${d.id}', '${e.id}', '${e.name}')" title="Delete">&times;</span>
                                    </span>
                                `).join('')}
                            </div>
                            <div class="add-form">
                                <input type="text" id="${inputId}" placeholder="New element..." onkeydown="if(event.key==='Enter') addElement('${d.id}', '${inputId}')" style="width: 100%;">
                                <button class="btn" onclick="addElement('${d.id}', '${inputId}')">+</button>
                            </div>
                        </div>
                    `;
                });
                dimContainer.innerHTML = dimHtml || '<div style="color: var(--muted);">No custom dimensions yet.</div>';

                // Choix des dimensions pour la creation de cube
                const pick = document.getElementById('dimPick');
                if (pick) {
                    pick.innerHTML = data.all_dimensions.length
                        ? data.all_dimensions.map(d => `<label style="font-size: 14px;"><input type="checkbox" value="${d.id}"> ${d.name}</label>`).join('')
                        : '<span style="color: var(--muted); font-size: 13px;">No dimension yet - create one below.</span>';
                }

                // Rendu des Cubes
                if (!data.cubes || data.cubes.length === 0) {
                    cubeContainer.innerHTML = `<div class="card">No cubes in this database.</div>`;
                    return;
                }

                let cubeHtml = '';
                data.cubes.forEach(cube => {
                    const dims = cube.dimensions;
                    cubeHtml += `
                        <div class="card">
                            <h2>Cube: ${cube.name}</h2>
                            <div class="meta">Dimensions: <b>${dims.map(d => d.name).join(' × ')}</b></div>
                    `;

                    if (dims.length === 2) {
                        const rowDim = dims[0];
                        const colDim = dims[1];
                        
                        cubeHtml += `<div class="filters" style="display:flex;gap:18px;flex-wrap:wrap;margin:14px 0;align-items:center">
                            <label style="font-size:13px;color:var(--muted)">Filter rows:
                                <select class="f-row" style="margin-left:6px">
                                    <option value="__all">All</option>${rowDim.elements.map(e => `<option value="${e.name}">${e.type === 4 ? '∑ ' : ''}${e.name}</option>`).join('')}
                                </select>
                            </label>
                            <label style="font-size:13px;color:var(--muted)">Filter columns:
                                <select class="f-col" style="margin-left:6px">
                                    <option value="__all">All</option>${colDim.elements.map(e => `<option value="${e.name}">${e.type === 4 ? '∑ ' : ''}${e.name}</option>`).join('')}
                                </select>
                            </label>
                            <span class="meta">Tip: edit a ∑ total cell to test splashing</span>
                        </div>`;
                        cubeHtml += `<table data-cube="${cube.id}"><thead><tr><th>${rowDim.name} × ${colDim.name}</th>`;
                        colDim.elements.forEach(c => {
                            cubeHtml += `<th data-col="${c.name}">${c.type === 4 ? '∑ ' : ''}${c.name}</th>`;
                        });
                        cubeHtml += `</tr></thead><tbody>`;

                        rowDim.elements.forEach(r => {
                            const isConsolRow = (r.type === 4);
                            cubeHtml += `<tr data-row="${r.name}" class="${isConsolRow ? 'consolidated-row' : ''}"><td>${isConsolRow ? '∑ ' : ''}${r.name}</td>`;
                            colDim.elements.forEach(c => {
                                const cellObj = cube.matrix[r.name]?.[c.name] || {value: 0, path: `${r.id},${c.id}`, is_consolidated: false};
                                const val = cellObj.value;
                                const path = cellObj.path;
                                const isConsolidated = cellObj.is_consolidated;
                                const numVal = typeof val === 'number' ? val : 0;
                                const displayVal = typeof val === 'number'
                                    ? val.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}) + ' €'
                                    : (val === '' || val === null || val === undefined
                                        ? '<span style="color:var(--muted)">0.0 €</span>' : val);
                                
                                cubeHtml += `<td data-col="${c.name}" class="editable ${isConsolidated ? 'consolidated' : ''}" 
                                                title="${isConsolidated ? 'Consolidated cell: the change will apply splashing' : 'Base cell'}"
                                                onclick="editCell(this, '${data.selected_db.id}', '${cube.id}', '${path}', ${numVal}, ${isConsolidated})">${displayVal}</td>`;
                            });
                            cubeHtml += `</tr>`;
                        });

                        cubeHtml += `</tbody></table>`;
                    } else {
                        cubeHtml += `<div class="meta" style="margin-top:10px;color:#fbbf24">
                            This cube has ${dims.length} dimensions: <b>${dims.map(d => d.name).join(' × ')}</b>.
                            The grid is displayed for cubes with exactly <b>two</b> dimensions — create a cube on two
                            dimensions to enter data here.</div>`;
                    }
                    cubeHtml += `</div>`;
                });

                cubeContainer.innerHTML = cubeHtml;

                // Filtres lignes / colonnes (slicing de la vue)
                cubeContainer.querySelectorAll('table[data-cube]').forEach(tbl => {
                    const card = tbl.closest('.card');
                    const rowSel = card.querySelector('.f-row');
                    const colSel = card.querySelector('.f-col');
                    const apply = () => {
                        const r = rowSel.value, c = colSel.value;
                        tbl.querySelectorAll('tbody tr').forEach(tr => {
                            tr.style.display = (r === '__all' || tr.dataset.row === r) ? '' : 'none';
                        });
                        tbl.querySelectorAll('[data-col]').forEach(el => {
                            el.style.display = (c === '__all' || el.dataset.col === c) ? '' : 'none';
                        });
                    };
                    rowSel.addEventListener('change', apply);
                    colSel.addEventListener('change', apply);
                });
            } catch (err) {
                cubeContainer.innerHTML = `<div class="card" style="color: #f87171;">Connection error: ${err.message}</div>`;
            }
        }
        loadData();
    </script>
</body>
</html>
"""
            self.wfile.write(html.encode('utf-8'))
        else:
            super().do_GET()

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), PaloViewerHandler) as httpd:
        print(f"Palo Web Studio (Splashing) running at http://localhost:{PORT}")
        httpd.serve_forever()
