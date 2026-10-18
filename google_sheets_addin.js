// ============================================================================
// PALO MOLAP Add-in pour Google Sheets
// ============================================================================
// Ce script permet de connecter directement Google Sheets à votre serveur PALO.
// Déployé sur votre VPS ou via un tunnel HTTPS.
// ============================================================================

// ⚠️ Configuration : remplacez par l'adresse publique de votre serveur PALO
const PALO_HOST = "http://VOTRE_VPS_IP:7777";
const PALO_USER = "admin";
const PALO_PASS_MD5 = "21232f297a57a5a743894a0e4a801fc3"; // MD5 de 'admin'

/**
 * Récupère ou met en cache le jeton de session PALO (SID)
 */
function getPaloSid() {
  const cache = CacheService.getScriptCache();
  let sid = cache.get("palo_sid");
  if (!sid) {
    const res = UrlFetchApp.fetch(`${PALO_HOST}/server/login?user=${PALO_USER}&password=${PALO_PASS_MD5}`);
    sid = res.getContentText().split(";")[0];
    cache.put("palo_sid", sid, 600); // Mise en cache pour 10 minutes
  }
  return sid;
}

/**
 * Lit une cellule dans un cube PALO depuis Google Sheets
 * 
 * Syntaxe dans une cellule :
 * =PALO_DATA("VentesDB", "ChiffreAffaires", "Janvier", "PC_Portable")
 * 
 * @customfunction
 */
function PALO_DATA(dbName, cubeName, mois, produit) {
  if (!dbName || !cubeName || !mois || !produit) return "";
  try {
    const sid = getPaloSid();
    const url = `${PALO_HOST}/cell/value?sid=${sid}&name_database=${encodeURIComponent(dbName)}&name_cube=${encodeURIComponent(cubeName)}&name_path=${encodeURIComponent(mois + ',' + produit)}`;
    const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const parts = response.getContentText().split(";");
    if (parts.length > 2) {
      return parseFloat(parts[2]);
    }
    return 0;
  } catch (e) {
    return "Erreur: " + e.message;
  }
}

/**
 * Met à jour une valeur dans PALO avec support optionnel du Splashing
 * 
 * Syntaxe :
 * =PALO_SET("VentesDB", "ChiffreAffaires", "Q1", "PC_Portable", 100000, 1)
 * 
 * @customfunction
 */
function PALO_SET(dbName, cubeName, mois, produit, valeur, splash) {
  try {
    const sid = getPaloSid();
    const splashMode = splash !== undefined ? splash : 1;
    const url = `${PALO_HOST}/cell/replace?sid=${sid}&name_database=${encodeURIComponent(dbName)}&name_cube=${encodeURIComponent(cubeName)}&name_path=${encodeURIComponent(mois + ',' + produit)}&value=${valeur}&splash=${splashMode}`;
    const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    return "OK: " + valeur;
  } catch (e) {
    return "Erreur: " + e.message;
  }
}

/**
 * Menu d'action dans Google Sheets
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('⚡ PALO MOLAP')
    .addItem('Tester la connexion', 'testConnection')
    .addToUi();
}

function testConnection() {
  try {
    const sid = getPaloSid();
    SpreadsheetApp.getUi().alert("✅ Succès ! Connecté au serveur PALO.\nJeton de session : " + sid);
  } catch(e) {
    SpreadsheetApp.getUi().alert("❌ Échec de connexion : " + e.message);
  }
}
