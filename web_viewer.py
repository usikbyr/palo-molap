#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import hashlib

PALO_URL = "http://127.0.0.1:7777"
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
    <title>PALO MOLAP Studio - Splashing</title>
    <style>
        :root {
            --bg: #090d16;
            --card: #131c2e;
            --border: #23324d;
            --text: #f8fafc;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --accent: #10b981;
            --danger: #ef4444;
            --purple: #a855f7;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 24px;
        }
        .container { max-width: 1100px; margin: 0 auto; }
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        h1 { font-size: 22px; font-weight: 700; color: var(--primary); }
        .badge {
            background: #064e3b;
            color: #34d399;
            padding: 5px 12px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
        }
        .controls {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }
        select, input[type="text"] {
            background: var(--card);
            color: var(--text);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
            outline: none;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
            margin-bottom: 24px;
        }
        h2 { font-size: 18px; margin-bottom: 8px; color: var(--text); }
        .meta { color: var(--muted); font-size: 14px; margin-bottom: 16px; }
        
        /* Table MOLAP */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            border-radius: 8px;
            overflow: hidden;
        }
        th, td {
            padding: 12px 18px;
            text-align: right;
            border: 1px solid var(--border);
            font-size: 14px;
        }
        th {
            background: #1e293b;
            color: var(--primary);
            font-weight: 600;
        }
        th:first-child, td:first-child {
            text-align: left;
            font-weight: 600;
            color: #e2e8f0;
            background: #172554;
        }
        td {
            background: #0b1322;
            font-variant-numeric: tabular-nums;
        }
        td.editable {
            cursor: pointer;
            transition: background 0.2s;
        }
        td.editable:hover {
            background: #1d2c47;
            outline: 2px solid var(--primary);
        }
        /* Style spécial pour les cellules consolidées (Splashing) */
        td.consolidated {
            background: #2e1065 !important;
            color: #d8b4fe !important;
            font-weight: 700;
        }
        td.consolidated:hover {
            outline: 2px solid var(--purple) !important;
            background: #3b0764 !important;
        }
        tr.consolidated-row td:first-child {
            background: #3b0764 !important;
            color: #f3e8ff !important;
            font-weight: 800;
        }
        td input {
            width: 100%;
            background: #020617;
            border: 1px solid var(--primary);
            color: #fff;
            padding: 6px 8px;
            text-align: right;
            border-radius: 4px;
            font-size: 14px;
            outline: none;
        }
        .total { font-weight: 700; color: #a7f3d0; background: #064e3b !important; }
        
        /* Dimensions Section */
        .dim-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-top: 10px;
        }
        .dim-card {
            background: #0b1322;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }
        .dim-title {
            font-size: 15px;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
        }
        .elem-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 16px;
        }
        .elem-chip {
            background: #1e293b;
            border: 1px solid var(--border);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .elem-chip.consolidated-chip {
            background: #3b0764;
            border-color: #7e22ce;
            color: #e9d5ff;
            font-weight: 600;
        }
        .elem-chip .del-btn {
            cursor: pointer;
            color: #94a3b8;
            font-size: 14px;
            font-weight: bold;
        }
        .elem-chip .del-btn:hover { color: var(--danger); }
        .add-form {
            display: flex;
            gap: 8px;
        }
        .btn {
            background: var(--primary);
            color: #0f172a;
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
            white-space: nowrap;
        }
        .btn:hover { opacity: 0.9; }
        .legend {
            display: flex;
            gap: 16px;
            align-items: center;
            font-size: 13px;
            color: var(--muted);
            margin-bottom: 16px;
            padding: 10px 14px;
            background: #0b1322;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        .legend-box {
            width: 14px;
            height: 14px;
            border-radius: 4px;
            display: inline-block;
            vertical-align: middle;
            margin-right: 6px;
        }
        #toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #10b981;
            color: #022c22;
            font-weight: 600;
            padding: 10px 18px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            display: none;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>PALO MOLAP Studio</h1>
                <div class="meta" style="margin: 0;">Gestion des Cubes & Moteur de Splashing</div>
            </div>
            <div style="display: flex; gap: 12px; align-items: center;">
                <span class="badge">● Connecté (Port 7777)</span>
                <button class="btn" onclick="loadData()">Actualiser</button>
            </div>
        </header>

        <div class="controls">
            <div style="display: flex; align-items: center; gap: 10px;">
                <label style="color: var(--muted); font-size: 14px;">Base de données :</label>
                <select id="dbSelect" onchange="loadData(this.value)"></select>
            </div>
        </div>

        <div class="legend">
            <span><span class="legend-box" style="background: #0b1322; border: 1px solid var(--border);"></span> Cellule de base (édition simple)</span>
            <span><span class="legend-box" style="background: #3b0764; border: 1px solid var(--purple);"></span> <b>Cellule Consolidée (SPLASHING)</b> : modifiez pour ventiler proportionnellement sur les enfants</span>
        </div>

        <!-- Section Cube -->
        <div id="cubeContent">Chargement du cube...</div>

        <!-- Section Dimensions & Éléments -->
        <div class="card">
            <h2>Gestion des Dimensions & Éléments</h2>
            <div class="meta">Les éléments en violet sont <b>consolidés</b> (regroupements hiérarchiques).</div>
            <div id="dimContent" class="dim-container"></div>
        </div>
    </div>

    <div id="toast">Opération réussie !</div>

    <script>
        let currentDbId = null;

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
                            showToast(`🌊 Splashing effectué : ${newVal.toLocaleString('fr-FR')} € ventilés sur les enfants !`);
                        } else {
                            showToast(`Cellule mise à jour : ${newVal.toLocaleString('fr-FR')} €`);
                        }
                        loadData(currentDbId);
                    } else {
                        alert('Erreur: ' + r.error);
                        td.textContent = oldVal.toLocaleString('fr-FR', {minimumFractionDigits: 1}) + ' €';
                    }
                } catch(e) {
                    alert('Erreur réseau: ' + e.message);
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
                    showToast(`Élément "${name}" ajouté avec succès`);
                    input.value = '';
                    loadData(currentDbId);
                } else {
                    alert('Erreur: ' + r.error);
                }
            } catch(e) {
                alert('Erreur réseau: ' + e.message);
            }
        }

        async function deleteElement(dimId, elemId, name) {
            if (!confirm(`Supprimer l'élément "${name}" de cette dimension ?`)) return;

            try {
                const res = await fetch('/api/element/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ database: currentDbId, dimension: dimId, element: elemId })
                });
                const r = await res.json();
                if (r.success) {
                    showToast(`Élément "${name}" supprimé`);
                    loadData(currentDbId);
                } else {
                    alert('Erreur: ' + r.error);
                }
            } catch(e) {
                alert('Erreur réseau: ' + e.message);
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
                    cubeContainer.innerHTML = `<div class="card" style="color: #f87171;">Erreur: ${data.error}</div>`;
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
                                <span style="font-size: 12px; color: var(--muted);">${d.elements.length} éléments</span>
                            </div>
                            <div class="elem-list">
                                ${d.elements.map(e => `
                                    <span class="elem-chip ${e.type === 4 ? 'consolidated-chip' : ''}">
                                        ${e.type === 4 ? '∑ ' : ''}${e.name}
                                        <span class="del-btn" onclick="deleteElement('${d.id}', '${e.id}', '${e.name}')" title="Supprimer">&times;</span>
                                    </span>
                                `).join('')}
                            </div>
                            <div class="add-form">
                                <input type="text" id="${inputId}" placeholder="Nouvel élément..." onkeydown="if(event.key==='Enter') addElement('${d.id}', '${inputId}')" style="width: 100%;">
                                <button class="btn" onclick="addElement('${d.id}', '${inputId}')">+</button>
                            </div>
                        </div>
                    `;
                });
                dimContainer.innerHTML = dimHtml || '<div style="color: var(--muted);">Aucune dimension personnalisée.</div>';

                // Rendu des Cubes
                if (!data.cubes || data.cubes.length === 0) {
                    cubeContainer.innerHTML = `<div class="card">Aucun cube présent dans cette base.</div>`;
                    return;
                }

                let cubeHtml = '';
                data.cubes.forEach(cube => {
                    const dims = cube.dimensions;
                    cubeHtml += `
                        <div class="card">
                            <h2>Cube : ${cube.name}</h2>
                            <div class="meta">Dimensions : <b>${dims.map(d => d.name).join(' × ')}</b></div>
                    `;

                    if (dims.length === 2) {
                        const rowDim = dims[0];
                        const colDim = dims[1];
                        
                        cubeHtml += `<table><thead><tr><th>${rowDim.name} \\ ${colDim.name}</th>`;
                        colDim.elements.forEach(c => {
                            cubeHtml += `<th>${c.type === 4 ? '∑ ' : ''}${c.name}</th>`;
                        });
                        cubeHtml += `</tr></thead><tbody>`;

                        rowDim.elements.forEach(r => {
                            const isConsolRow = (r.type === 4);
                            cubeHtml += `<tr class="${isConsolRow ? 'consolidated-row' : ''}"><td>${isConsolRow ? '∑ ' : ''}${r.name}</td>`;
                            colDim.elements.forEach(c => {
                                const cellObj = cube.matrix[r.name]?.[c.name] || {value: 0, path: `${r.id},${c.id}`, is_consolidated: false};
                                const val = cellObj.value;
                                const path = cellObj.path;
                                const isConsolidated = cellObj.is_consolidated;
                                const numVal = typeof val === 'number' ? val : 0;
                                const displayVal = typeof val === 'number' ? val.toLocaleString('fr-FR', {minimumFractionDigits: 1, maximumFractionDigits: 1}) + ' €' : val;
                                
                                cubeHtml += `<td class="editable ${isConsolidated ? 'consolidated' : ''}" 
                                                title="${isConsolidated ? 'Cellule consolidée : le changement appliquera un Splashing' : 'Cellule de base'}"
                                                onclick="editCell(this, '${data.selected_db.id}', '${cube.id}', '${path}', ${numVal}, ${isConsolidated})">${displayVal}</td>`;
                            });
                            cubeHtml += `</tr>`;
                        });

                        cubeHtml += `</tbody></table>`;
                    }
                    cubeHtml += `</div>`;
                });

                cubeContainer.innerHTML = cubeHtml;
            } catch (err) {
                cubeContainer.innerHTML = `<div class="card" style="color: #f87171;">Erreur de connexion: ${err.message}</div>`;
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
        print(f"Serveur Web Studio Palo avec Splashing démarré sur http://localhost:{PORT}")
        httpd.serve_forever()
