backend/data-generator — Répertoire intentionnellement vide

Ce dossier est vide par conception.

Pourquoi il existe ?

Le `Dockerfile` du backend fait `COPY . .` depuis le contexte `backend/`.
Docker ne peut pas accéder à des fichiers en dehors du contexte de build,
donc le vrai générateur (`data-generator/` à la racine du projet) ne peut
pas être copié dans l'image lors du `docker build`.

Le vrai générateur

Le générateur se trouve à `data-generator/generator.py` (racine du projet).

Comment il est rendu disponible dans le container

`docker-compose.yml` monte le générateur comme volume au runtime :
```yaml
volumes:
  - ./data-generator:/app/data-generator   # ← écrase ce dossier vide
```

Quand `make train` s'exécute dans le container `/app/data-generator/generator.py`
est disponible et `train.py` peut faire `from generator import generate_training_dataset`.

Ne pas supprimer ce dossier

Sans lui, Docker créerait un répertoire `/app/data-generator` inexistant
avant le montage du volume, ce qui peut causer des erreurs selon la version
de Docker Compose.
