# PariMatchia Bot

Bot Python (FastAPI + Playwright) qui place des paris sur **coteetsport.ma**
et renvoie le **code-barres de réservation** (Code 128) à l'application Lovable.

## 1. Variables d'environnement (Railway → Variables)

| Variable | Obligatoire | Description |
|---|---|---|
| `API_TOKEN` | ✅ | Chaîne aléatoire 64 caractères. À copier aussi dans Lovable (secret `BOT_API_TOKEN`). |
| `CAPTCHA_API_KEY` | ✅ | Votre clé 2captcha. |
| `TARGET_URL` | ✅ | `https://www.coteetsport.ma/` |
| `RECAPTCHA_SITEKEY` | ⛔ | Sitekey reCAPTCHA (à récupérer dans le HTML de la page de réservation). |
| `HEADLESS` | ⛔ | `true` (défaut). |

## 2. Déploiement Railway

1. Pousser tous les fichiers de ce dossier sur un repo GitHub.
2. railway.app → New Project → Deploy from GitHub → sélectionner le repo.
3. Variables → ajouter les variables ci-dessus.
4. Settings → Networking → Generate Domain → copier l'URL publique.
5. Dans Lovable, page Bot Setup → coller cette URL dans `BOT_RAILWAY_URL`.

## 3. Endpoints

- `GET  /health`
- `POST /reserve` body `{"selections":[{"id":"123_2"}],"stake":50}`
  Header `Authorization: Bearer <API_TOKEN>`

## 4. ⚠️ Adapter les sélecteurs CSS dans executor.py

Le DOM de coteetsport.ma change. Inspectez le site et adaptez les `# TODO`.

## 5. Test local

```bash
pip install -r requirements.txt
playwright install chromium
cp env.example .env  # puis remplir
uvicorn main:app --reload
```
