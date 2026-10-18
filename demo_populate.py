#!/usr/bin/env python3
import urllib.request
import urllib.parse
import hashlib
import time

BASE_URL = "http://127.0.0.1:7777"

def palo_get(path, params=None):
    if params:
        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    else:
        url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode('utf-8').strip()

def main():
    print("=== 1. Authentification ===")
    pwd_md5 = hashlib.md5("admin".encode('utf-8')).hexdigest()
    res = palo_get("/server/login", {"user": "admin", "password": pwd_md5})
    sid = res.split(";")[0]
    print(f"Connexion réussie ! Session SID: {sid}")

    timestamp = int(time.time())
    db_name = f"VentesDB_{timestamp}"
    print(f"\n=== 2. Création de la Base de Données '{db_name}' ===")
    res = palo_get("/database/create", {"sid": sid, "new_name": db_name})
    db_id = res.split(";")[0]
    print(f"Base de données créée (ID: {db_id})")

    print("\n=== 3. Création des Dimensions et Éléments ===")
    # Dimension Mois
    res = palo_get("/dimension/create", {"sid": sid, "database": db_id, "new_name": "Mois"})
    dim_mois = res.split(";")[0]
    print(f"Dimension 'Mois' créée (ID: {dim_mois})")

    mois_elements = ["Janvier", "Fevrier", "Mars"]
    mois_ids = {}
    for m in mois_elements:
        res = palo_get("/element/create", {"sid": sid, "database": db_id, "dimension": dim_mois, "new_name": m, "type": 1})
        mois_ids[m] = res.split(";")[0]
        print(f"  -> Mois: {m} (ID: {mois_ids[m]})")

    # Dimension Produits
    res = palo_get("/dimension/create", {"sid": sid, "database": db_id, "new_name": "Produits"})
    dim_prod = res.split(";")[0]
    print(f"Dimension 'Produits' créée (ID: {dim_prod})")

    produits_elements = ["PC_Portable", "Ecran_4K", "Clavier_Meca"]
    prod_ids = {}
    for p in produits_elements:
        res = palo_get("/element/create", {"sid": sid, "database": db_id, "dimension": dim_prod, "new_name": p, "type": 1})
        prod_ids[p] = res.split(";")[0]
        print(f"  -> Produit: {p} (ID: {prod_ids[p]})")

    print("\n=== 4. Création du Cube 'ChiffreAffaires' ===")
    dim_list = f"{dim_mois},{dim_prod}"
    res = palo_get("/cube/create", {"sid": sid, "database": db_id, "new_name": "ChiffreAffaires", "dimensions": dim_list})
    cube_id = res.split(";")[0]
    print(f"Cube 'ChiffreAffaires' créé (ID: {cube_id})")

    print("\n=== 5. Insertion des Données MOLAP ===")
    donnees = [
        ("Janvier", "PC_Portable", 12500.0),
        ("Janvier", "Ecran_4K", 4200.0),
        ("Janvier", "Clavier_Meca", 890.0),
        ("Fevrier", "PC_Portable", 15800.0),
        ("Fevrier", "Ecran_4K", 3900.0),
        ("Fevrier", "Clavier_Meca", 1120.0),
        ("Mars", "PC_Portable", 18200.0),
        ("Mars", "Ecran_4K", 5100.0),
        ("Mars", "Clavier_Meca", 1450.0),
    ]

    for m, p, val in donnees:
        path = f"{mois_ids[m]},{prod_ids[p]}"
        palo_get("/cell/replace", {
            "sid": sid,
            "database": db_id,
            "cube": cube_id,
            "path": path,
            "value": val
        })
        print(f"  [+] Cellule ({m:<8}, {p:<12}) = {val:>8.1f} €")

    print("\n=== 6. Lecture & Vérification des Données ===")
    path_test = f"{mois_ids['Fevrier']},{prod_ids['PC_Portable']}"
    res_val = palo_get("/cell/value", {
        "sid": sid,
        "database": db_id,
        "cube": cube_id,
        "path": path_test
    })
    valeur_reelle = res_val.split(";")[2]
    print(f"Interrogation de la cellule (Février, PC_Portable) : {valeur_reelle} €")

    print("\n=== 7. Persistance sur le disque ===")
    palo_get("/database/save", {"sid": sid, "database": db_id})
    print("Base de données sauvegardée avec succès dans ./palo-data/")

if __name__ == "__main__":
    main()
