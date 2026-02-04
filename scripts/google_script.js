function processWebhookTransfer() {
  // --- CONFIGURATION ---
  // L'URL de votre route "Ingress" créée à l'étape précédente en Python
  const SERVER_URL = "https://render-signal-server-latest.onrender.com/api/ingress/gmail";
  // Le token défini dans votre fichier settings.py (PROCESS_API_TOKEN)
  const API_TOKEN = PropertiesService.getScriptProperties().getProperty("PROCESS_API_TOKEN") || "";
  // Le nom exact du libellé créé dans Gmail
  const LABEL_NAME = "A_TRANSFERER_WEBHOOK";
  // ---------------------

  if (!API_TOKEN) {
    console.log("PROCESS_API_TOKEN manquant dans les Script Properties.");
    return;
  }

  const label = GmailApp.getUserLabelByName(LABEL_NAME);
  
  // Sécurité : si le libellé n'existe pas encore
  if (!label) {
    console.log("Le libellé " + LABEL_NAME + " n'existe pas.");
    return;
  }

  // On cherche les threads qui ont ce label ET qui sont non lus 
  // (pour éviter de renvoyer 50 fois le même historique)
  const threads = label.getThreads(0, 20); // Traite par lot de 20 max pour éviter timeout

  if (threads.length === 0) {
    console.log("Aucun mail à traiter.");
    return;
  }

  for (const thread of threads) {
    const messages = thread.getMessages();
    
    for (const message of messages) {
      // On ne traite que les messages non lus du fil de discussion
      if (message.isUnread()) {
        
        const payload = {
          "subject": message.getSubject(),
          "sender": message.getFrom(), // "Nom <email@domaine.com>"
          "date": message.getDate().toISOString(),
          "body": message.getBody(), // On envoie le HTML pour que votre extracteur de lien fonctionne
          "snippet": message.getPlainBody().substring(0, 200) // Pour les logs
        };

        const options = {
          "method": "post",
          "contentType": "application/json",
          "headers": {
            "Authorization": "Bearer " + API_TOKEN,
            "X-Source": "GoogleAppsScript"
          },
          "payload": JSON.stringify(payload),
          "muteHttpExceptions": true // Pour pouvoir lire le corps de l'erreur si échec
        };

        try {
          const response = UrlFetchApp.fetch(SERVER_URL, options);
          const responseCode = response.getResponseCode();
          
          if (responseCode === 200) {
            console.log("Succès pour : " + payload.subject);
            // Marquer comme lu pour ne pas le renvoyer au prochain tour
            message.markRead();
          } else {
            console.error("Erreur Serveur (" + responseCode + ") : " + response.getContentText());
            // On laisse en "non lu" pour retenter plus tard, ou on loggue l'erreur
          }
        } catch (e) {
          console.error("Erreur de connexion : " + e.toString());
        }
      }
    }
    
    // Une fois le thread traité, on retire le label "A_TRANSFERER_WEBHOOK" 
    // pour nettoyer la boite de réception visuellement (optionnel)
    thread.removeLabel(label);
  }
}
