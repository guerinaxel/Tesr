# AI Code Assistant – Frontend (Angular 20)

Ce frontend Angular offre une interface de chat moderne permettant
d’interroger le backend Django / RAG.  
Il s’agit d’un composant standalone simple, extensible et responsive.

---

## ✨ Fonctionnalités

- UI de chat minimaliste mais extensible.
- Composants Angular standalone (Angular 20).
- Envoi de requêtes vers `/api/code-qa/`.
- Gestion du flux dialogué (messages utilisateur / IA).
- SCSS responsive.

---

## 📁 Structure du frontend

```
frontend/
├── package.json
├── angular.json
├── tsconfig.json
└── src/
    ├── main.ts
    ├── app/
    │   ├── app.routes.ts
    │   └── chat/
    │       ├── chat.component.ts
    │       ├── chat.component.html
    │       └── chat.component.scss
    └── environments/
        ├── environment.ts
        └── environment.prod.ts
```

---

## 📦 Dépendances

- Angular 20
- RxJS
- TypeScript
- SCSS
- HttpClient (built-in)

Installer :

```bash
npm install
```

---

## 🛠️ Installation

### 1. Cloner le projet

```bash
git clone <votre-repo>
cd frontend
```

### 2. Installer les dépendances

```bash
npm install
```

### 3. Lancer l’app en développement

```bash
ng serve
```

Disponible sur :

```
http://localhost:4200
```

---

## 🤖 Fonctionnement du chat

Le composant envoie une requête HTTP :

```ts
this.http.post('/api/code-qa/', { question: this.question })
```

La réponse est affichée dans la liste des messages :

```json
{
  "answer": "Explication basée sur le code indexé..."
}
```

---

## 🔧 Configuration API

Modifier `environment.ts` :

```ts
export const environment = {
  apiUrl: '/api'
};
```

Ou :

```ts
apiUrl: 'http://localhost:8000/api'
```

---

## 📱 Styles & UX

- SCSS composant
- Classes `.user` pour aligner les messages à droite
- Scroll auto intégré via container flex

---

## 🚀 Build production

```bash
ng build --configuration production
```

Build output :

```
dist/frontend/
```

---

## 🧩 Personnalisation

- Ajouter un loader IA
- Ajouter la streaming API (SSE)
- Ajouter une sidebar de navigation
- Intégration Material ou Tailwind

---

## 📄 Licence

MIT (modifiable selon votre projet).
