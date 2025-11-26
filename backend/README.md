# AI Code Assistant – Backend (Django + RAG + Ollama)

Ce backend fournit une API permettant d’interroger votre base de code (Python, Django, Angular…)
à l’aide d’un modèle LLaMA 3.1 exécuté via **Ollama**.  
Le modèle génère ses réponses en utilisant la technique **RAG (Retrieval-Augmented Generation)** :
votre code est indexé, vectorisé, puis utilisé comme contexte pertinent pour chaque requête.

---

## ✨ Fonctionnalités

- Extraction automatique du code du projet (backend + frontend).
- Découpage intelligent en chunks pour du contexte précis.
- Vectorisation via `nomic-ai/nomic-embed-text-v1.5` (Sentence Transformers).
- Index FAISS rapide et persistant (`rag_index.faiss`).
- API REST `/api/code-qa/` pour poser des questions sur le code.
- Intégration Ollama + LLaMA 3.1 locale.
- Commande Django : `build_rag_index` pour reconstruire l’index.

---

## 📁 Structure du backend

```
backend/
├── project/
├── codeqa/
│   ├── rag_index.py
│   ├── rag_service.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   └── management/
│        └── commands/
│              └── build_rag_index.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

## 📦 Dépendances

### Python
- Django 5
- Django REST Framework
- sentence-transformers
- sentencepiece (requis par `nomic-ai/nomic-embed-text-v1.5`)
- Nomic client (pour les embeddings `nomic-embed-*`)
- FAISS CPU
- Ollama Python client
- python-dotenv

Installables via :

```bash
pip install -r requirements.txt
```

### Système
- Docker (optionnel mais recommandé)
- Ollama installé localement  
  → https://ollama.com/download

---

## 🛠️ Installation

### 1. Cloner le projet

```bash
git clone <votre-repo>
cd backend
```

### 2. Créer un environnement Python

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer Ollama + LLaMA

```bash
ollama pull llama3.1:8b
```

### 5. Configurer l’environnement

Créer `.env` :

```
DJANGO_DEBUG=True
OPENAI_API_KEY=  # vide si pas utilisé
```

### 6. Appliquer les migrations Django

```bash
python manage.py migrate
```

### 7. Construire l’index RAG

```bash
python manage.py build_rag_index
```

Cela génère :

```
rag_index.faiss
rag_docs.pkl
```

---

## ▶️ Lancement du serveur

### Option A — Python local

```bash
python manage.py runserver
```

### Option B — Docker (backend + Ollama)

```bash
docker compose up --build
```

---

## 🤖 Utilisation de l’API

### Endpoint : `POST /api/code-qa/`

#### Exemple de requête :

```json
{
  "question": "À quoi sert le fichier models.py dans l’app accounts ?"
}
```

#### Exemple de réponse :

```json
{
  "answer": "Le fichier models.py définit les modèles ORM..."
}
```

---

## 🧩 Personnalisation

- Ajouter ou exclure certaines extensions → `ALLOWED_EXT` dans `rag_index.py`
- Modifier le modèle d’embedding → variable d’environnement `RAG_EMBED_MODEL` (par défaut `nomic-ai/nomic-embed-text-v1.5`).
- Définir un modèle de secours en cas d’échec de téléchargement → `RAG_EMBED_MODEL_FALLBACK` (par défaut `sentence-transformers/all-MiniLM-L6-v2`).
- Le backend reconstruit automatiquement l’index FAISS si la dimension des embeddings change (ex. passage d’un ancien modèle vers Nomic).
- Augmenter la profondeur RAG → `k=5` → `k=10`

---

## ✅ Tests & couverture

Lancer les tests avec la couverture obligatoire (≥ 80 %) :

```bash
python manage.py test
```

Les rapports XML JUnit et `coverage.xml` sont générés dans `test-results/` et le build échoue automatiquement si le seuil est franchi.

---

## 🛡️ Sécurité

- Pas d’accès au système de fichiers via l’API.
- Index généré une fois, non reconstruit à chaque requête.
- Aucune donnée envoyée à des services externes (exécution 100% locale).

---

## 📄 Licence

MIT (modifiable selon votre projet).
