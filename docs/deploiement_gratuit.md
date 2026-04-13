# Deploiement gratuit d'AgroX (sans Render)

Ce guide permet de publier AgroX gratuitement si les limites Render sont atteintes.

## Option 1 (recommandee): Hugging Face Spaces (Docker)

Avantages:
- Gratuit
- Public par URL
- Compatible avec votre Dockerfile existant
- Simple a maintenir

### Etapes

1. Creez un compte Hugging Face.
2. Creez un nouveau Space:
   - Type: `Docker`
   - Visibilite: `Public`
3. Poussez votre code dans le repository du Space.
4. Ajoutez les variables d'environnement dans les Settings du Space:
   - `ADMIN_API_KEY` = votre cle admin (facultatif mais recommande)
   - `PORT` = `7860`
5. Le build se lance automatiquement.
6. Ouvrez l'URL publique du Space.

### Verification rapide apres deploiement

- `GET /health` doit retourner `{"statut":"ok", ...}`
- `GET /ready` doit retourner un statut `ready`
- Testez ensuite `POST /predict`

## Option 2: PythonAnywhere (plan gratuit)

Avantages:
- Gratuit
- Bon pour Flask simple

Limites:
- Ressources plus limitees
- Configuration WSGI manuelle

Etapes generales:
1. Creez un compte PythonAnywhere.
2. Creez une Web App Flask.
3. Uploadez le code.
4. Installez les dependances via `pip install -r requirements.txt` dans votre venv.
5. Configurez le fichier WSGI pour pointer vers `app`.
6. Redemarrez la web app.

## Notes importantes

- Si vous poussez ce projet vers un nouveau repo (Space), incluez les dossiers `model/` et `data/` necessaires au demarrage.
- Si vous ne voulez pas exposer les donnees locales historiques, vous pouvez supprimer `data/history.db` avant publication.
- En gratuit, le service peut dormir apres inactivite (normal).

## Commandes locales utiles avant push

```bash
python train_model.py
python app.py
```

Puis verifier:

```bash
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5001/ready
```
