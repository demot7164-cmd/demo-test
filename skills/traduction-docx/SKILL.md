# Skill: Traduction DOCX

## Description
Traduire des fichiers DOCX vers l'une des 10 langues les plus parlées en conservant **exactement** la mise en forme.

## Fonctionnalités
- **Préservation totale de la mise en forme** : tableaux, en-têtes, pieds de page, notes de bas de page, styles, couleurs, images
- **Traduction précise** : utilise mistral-medium-latest pour une traduction de qualité professionnelle
- **Gestion des runs** : conserve le gras, l'italique et autres styles au mot près
- **Traitement par lots** : optimisé pour les documents longs

## Langues supportées
- Anglais (en)
- Espagnol (es)
- Allemand (de)
- Italien (it)
- Portugais (pt)
- Russe (ru)
- Chinois (zh)
- Japonais (ja)
- Arabe (ar)
- Hindi (hi)

## Utilisation

### Depuis Vibe Work
1. Appeler le workflow `docx-translation`
2. Sélectionner le fichier DOCX à traduire
3. Choisir la langue cible parmi : en, es, de, it, pt, ru, zh, ja, ar, hi
4. Le workflow retourne un lien de téléchargement vers le fichier traduit

### Paramètres
- `langue_cible` (requis) : Code de la langue cible (ex: "fr", "es", "de")

### Sortie
- Lien de téléchargement vers le fichier DOCX traduit
- Le fichier est disponible pendant 24 heures

## Exemple de document test
Un document DOCX valide pour tester cette skill doit contenir :
- En-tête avec texte
- Pied de page avec texte
- Tableau coloré
- Texte avec mots en gras au milieu de phrases
- Note de bas de page

Après traduction, **tout** doit être conservé à l'identique, sauf le texte.

## Configuration requise
- Variable d'environnement `MISTRAL_API_KEY` : Clé API Mistral valide
- Modèle : mistral-medium-latest (utilisé par défaut)

## Implémentation technique
- **Workflow** : `docx-translation` (hérite de `InteractiveWorkflow`)
- **Activités** :
  - `download_file` : Télécharge le fichier depuis l'URL
  - `extract_text_with_runs` : Extrait le texte avec les balises de runs <r0>, <r1>, etc.
  - `translate_with_mistral` : Appelle l'API Mistral (mistral-medium-latest) pour la traduction
  - `replace_text_in_docx` : Remplace le texte dans le DOCX original en conservant toute la mise en forme
  - `upload_file` : Upload le fichier traduit
  - `get_signed_url` : Génère un lien de téléchargement valide 24h

## Déploiement
1. Installer les dépendances : `make install`
2. Démarrer le worker : `make start-worker`
3. Le workflow sera automatiquement enregistré

## Tests
Des tests sont disponibles pour vérifier :
- La préservation des tableaux
- La préservation des en-têtes et pieds de page
- La conservation du gras dans le texte
- La conservation des notes de bas de page

## Remarques
- Le workflow ne crée **jamais** de nouveau Document. Il ouvre le DOCX original et remplace uniquement le texte des balises w:t
- Chaque paragraphe est envoyé avec ses runs balisés <r1>…</r1> pour garder le gras au mot près
- Aucune opération non déterministe (time, random) dans le code du workflow, seulement dans les activités
