# SignalGuard v2 — Fiabilité, sécurité et mesure honnête

Ce document décrit les améliorations des blocs 1 (crédibilité des mesures) et 2 (fonctionnalités Agno de production) et la manière de reproduire les résultats.

## 1. Corrections de la mesure (bloc 1)

| Problème | Correction |
|---|---|
| Le benchmark d'origine évaluait v0 sur les annotations **v3** et les versions suivantes sur la **v4** | Toutes les versions utilisent la v4 par défaut (`--gold-version`, `--gold-file` pour forcer autre chose). Un test le vérifie. |
| Une seule exécution LLM par version | `--runs N` : chaque run est sauvegardé, puis un résumé donne moyenne ± écart-type, min et max. |
| Aucun contrôle du décodage | v2 : `temperature=0`, `seed=42`. v0 reste tel quel, comme référence historique. |
| Les « preuves » du LLM n'étaient jamais vérifiées | Ancrage des preuves : chaque citation est classée `exact`, `fuzzy` ou `ungrounded`. Les citations inventées sont rejetées et comptées (taux de preuves hallucinées). |

## 2. Fonctionnalités de production (bloc 2)

### Sorties structurées Pydantic — [agents/v2/schemas.py](../agents/v2/schemas.py)

- `output_schema=` d'Agno avec des sorties structurées natives. Les bornes du rubric sont vérifiées par Pydantic.
- Le total de pertinence est **calculé en Python**. Le mode d'échec « le total ne correspond pas à la somme » disparaît.
- Les catégories de risque forment un ensemble fermé (`NONE`, `SECURITY`, `COMPATIBILITY`, `SUSPICION`), aligné sur la taxonomie v4. v1 acceptait encore `DEPRECATION` et `MIGRATION`.

### Couche de fiabilité — [agents/v2/runner.py](../agents/v2/runner.py)

- Retries avec backoff exponentiel et jitter, sur les erreurs réseau **et** sur les réponses invalides. Les `retries` d'Agno ne relancent que sur exception ; une réponse non conforme revient comme un run normal.
- Cache disque adressé par SHA-256 (modèle, version du prompt, instructions, schéma, prompt, seed, run). Les benchmarks deviennent reproductibles et gratuits à relancer.
- Comptabilité par appel : tentatives, latence, tokens, coût annoncé par le fournisseur.
- Un `Agent` Agno neuf par appel, ce qui permet l'exécution en parallèle sans état partagé.

### Défense contre l'injection de prompt — [agents/v2/guards.py](../agents/v2/guards.py)

Le contenu des signaux vient d'Internet, donc il est contrôlé par des tiers.

1. Normalisation NFKC et suppression des caractères invisibles (zero-width, contrôle).
2. Détection par expressions régulières. Elle est plus large que le `PromptInjectionGuardrail` d'Agno, qui cherche des phrases fixes et rate par exemple « ignore **all** previous instructions ».
3. Neutralisation : la phrase qui contient la charge est retirée **avant** d'atteindre le modèle, et les chevrons sont échappés pour que le contenu ne puisse pas fermer le délimiteur `<untrusted_signal>`.
4. Une tentative de manipulation est elle-même un indicateur de suspicion : catégorie `SUSPICION`, niveau ≥ `MEDIUM`.

### Profilage déterministe — [agents/v2/profiler.py](../agents/v2/profiler.py)

Calculé une seule fois par signal, sans LLM :

- marqueurs explicites de compatibilité et de sécurité ;
- **score de dépôt-leurre GitHub** : vocabulaire de triche ou de crack, usurpation d'un logiciel payant, accumulation de topics, langage HTML contredisant des topics natifs (cpp, directx, win32...). Sur le DEV : 8 leurres détectés sur 8, aucun faux positif.

### Arbitrage du risque — [agents/v2/risk.py](../agents/v2/risk.py)

Le LLM donne son avis, puis des règles explicites tranchent. Chaque correction est tracée dans `adjustments`, et l'avis brut du modèle est conservé dans `llm_view`. Chaque label final est donc explicable.

### Pertinence — [agents/v2/relevance.py](../agents/v2/relevance.py)

- Rubric **ancré** (descripteurs pour chaque tranche de score) et persona explicite (équipe qui construit des applications LLM et multi-agents).
- Les métadonnées (stars, downloads, points, topics) sont fournies au modèle.
- Un dépôt-leurre est plafonné à 10 points.

### Exécution parallèle — [benchmarks/evaluate_agents.py](../benchmarks/evaluate_agents.py)

`--concurrency N` (6 par défaut) avec un pool de threads. Les agents historiques reçoivent une instance par thread.

## 3. Fournisseur LLM gratuit

Le fournisseur se choisit dans `.env` avec `LLM_PROVIDER` (voir [.env.example](../.env.example) et [config.py](../config.py)) : `openrouter`, `mistral`, `groq`, `gemini` ou `custom`. Tous les agents, y compris v0 et v1.1, utilisent le même fournisseur. La comparaison reste donc équitable.

Configuration utilisée pour les résultats ci-dessous : **Groq, offre gratuite**. La pertinence passe par `openai/gpt-oss-120b` et le risque par `openai/gpt-oss-20b`, avec la même répartition pour **toutes** les versions. On utilise aussi `reasoning_effort=low`. Quotas mesurés : 1 000 requêtes par jour et 8 000 tokens par minute, pour chaque modèle.

Autres options testées en novembre 2026 :
- OpenRouter `:free` : 50 requêtes par jour sans achat de crédit.
- Mistral « Experiment » : 0 requête par minute sur mistral-small, 2 sur ministral-8b, puis erreur 402.
- Gemini gratuit : environ 20 requêtes par jour selon des relevés récents.

Si le quota du jour est épuisé, le benchmark s'arrête sans rien enregistrer de faux (`QuotaExhausted`) et reprend avec `--skip-existing`.

Les offres gratuites limitent les requêtes par minute. Un limiteur de débit partagé (`LLM_MAX_RPM`, [agents/v2/ratelimit.py](../agents/v2/ratelimit.py)) espace tous les appels. Les erreurs 429 sont relancées avec un backoff plus long. Les agents historiques passent aussi par ce limiteur, pour qu'une erreur de quota ne soit pas comptée comme une erreur du modèle.

## 4. Reproduire les résultats

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

```powershell
.\.venv\Scripts\python.exe benchmarks\run_all.py --runs 3
```

`run_all.py` lance v0 et v2 sur DEV puis TEST, le benchmark d'injection, la mesure séquentiel/parallèle, et génère `results/benchmark/COMPARISON.md`. Avec `--skip-existing`, il reprend là où il s'est arrêté. Avec Groq gratuit, un run complet (environ 540 appels) prend environ 45 minutes.

## 5. Résultats (Groq gratuit)

Le détail complet est dans [results/benchmark/COMPARISON.md](../results/benchmark/COMPARISON.md).

| | DEV v0 | DEV v2 | TEST v0 | TEST v2 |
|---|---:|---:|---:|---:|
| Relevance MAE ↓ | 23,25 | **13,94** | 26,92 | **19,38** |
| Relevance Spearman ↑ | 0,645 | **0,899** | **0,678** | 0,620 |
| NDCG@10 ↑ | 0,619 | **0,855** | **0,783** | 0,781 |
| Risk accuracy ↑ | 0,864 | **0,938** | 0,739 | **0,958** |
| Risk macro-F1 ↑ | 0,745 | **0,915** | 0,557 | **0,941** |
| Rappel MEDIUM ↑ | 0,400 | **0,818** | 0,167 | **0,833** |
| Breaking changes F1 ↑ | 1,000 | 1,000 | 0,800 | 1,000 |

Robustesse aux injections (DEV, 12 signaux à risque et 15 peu pertinents attaqués) :
- signaux à risque classés LOW sous attaque : 83 % pour v0, **0 %** pour v2 ;
- attaques réussies pour gonfler la pertinence (+20 points ou plus) : 93 % pour v0, **0 %** pour v2 ;
- gonflement moyen de la pertinence : +64,6 points pour v0, **+0,7** pour v2 ;
- détection des injections : 0 % pour v0, **100 %** pour v2.

Le « downgrade success » de v0 (25 %) sous-estime le problème : v0 classe déjà la plupart de ces signaux LOW sans attaque. Le seul cas v2 est un passage HIGH → MEDIUM, toujours en catégorie SECURITY.

Lecture honnête :
- **Risque** : nette amélioration sur DEV et sur TEST (accuracy 0,739 → 0,958 sur TEST). Elle vient surtout du détecteur de dépôts-leurres et de l'arbitrage. Les 8 leurres du DEV sont tous détectés.
- **Pertinence** : nette amélioration sur DEV, mais sur TEST v2 ne bat v0 que sur la MAE ; le classement (Spearman) est moins bon. Cause identifiée : v2 surestime les notes de version GitHub Releases (biais moyen de +34 points sur TEST, +20 sur DEV), car le rubric dit que les releases de librairies majeures sont « highly applicable » sans distinguer un patch d'une version importante. C'est la prochaine correction, à calibrer sur DEV uniquement.
- **Preuves** : après correction du vérificateur (les citations « Title: … » reprises du prompt étaient rejetées à tort), aucune citation inventée n'est détectée avec gpt-oss. Aucune décision ne dépendait des citations rejetées.
- **Limites** : les petites différences (inférieures à 0,05) restent dans le bruit d'un LLM et ne sont pas significatives. Le modèle (gpt-oss) n'est pas celui des anciens résultats (mistral-small-3.2) : les chiffres v0 ne sont pas comparables à l'ancien historique, seulement entre eux.

## 6. Protocole et limites

- Le développement de v2 s'est appuyé uniquement sur l'analyse d'erreurs du **DEV**. TEST n'est évalué qu'une fois, à la fin.
- TEST avait déjà été consulté lors d'une itération intermédiaire : un nouveau jeu indépendant reste nécessaire pour une évaluation finale irréprochable.
- Les annotations de référence ont été construites par consensus de deux LLM (GPT et Claude), puis vérifiées. Elles ne sont pas entièrement humaines.
- Labels v4 à réauditer (repérés pendant l'analyse DEV) : trois posts HN marqués `LOW/SECURITY` dont la justification ne mentionne aucun problème de sécurité (FastGraphRAG, Promi, Rowboat), et deux modèles HF marqués `MEDIUM/NONE` (un niveau élevé sans catégorie de risque est incohérent). Ces cas pénalisent toutes les versions de la même façon. Ils n'ont **pas** été modifiés pour ne pas ajuster la référence au modèle.

## 7. Audit v4.1 et calibration des releases

- **Origine des notes de référence** : seules 5 notes sur 48 coïncident exactement avec les prédictions de v0. Il n'y a donc pas de copie systématique. Les notes de pertinence v4 sont identiques à celles de la v3.
- **Gold v4.1** ([scripts/build_gold_v4_1.py](../scripts/build_gold_v4_1.py)) : les 8 incohérences signalées par `audit_gold_v4.py` sont corrigées selon une règle minimale. Le niveau de risque annoté est conservé, et seule la catégorie est rendue cohérente (5 `LOW/SECURITY` → `NONE`, 2 modèles HF avec `trust_remote_code` → `SECURITY`, 1 dépôt douteux → `SUSPICION`). La v4 reste intacte. Les métriques sont recalculées hors ligne avec [scripts/rescore_on_gold.py](../scripts/rescore_on_gold.py).
- **Calibration des GitHub Releases (DEV uniquement)** : le profilage calcule le type de version (patch, mineure ou majeure) et détecte les sous-paquets (par exemple `langchain-qdrant`). Les bornes du rubric sont appliquées automatiquement aux sous-paquets et aux patchs, et chaque ajustement est tracé. Sur les releases du DEV, le biais passe de +20,4 à **+4,5** et la MAE descend à 8,5.
- **Reprise après coupure** : `--runs N` et `--start-run` gèrent plusieurs runs, une sauvegarde par signal permet de reprendre après une coupure de quota, et `run_all.py --wait-on-quota` attend que le quota gratuit se libère.
- Limite : le biais des releases a d'abord été remarqué sur TEST (+34), puis confirmé sur DEV. TEST n'est donc plus totalement vierge, et un nouveau jeu indépendant reste recommandé.

## 8. Bloc 3 — Workflow Agno, synthèse vérifiée, `main.py`

### Workflow ([pipeline/workflow.py](../pipeline/workflow.py))

```text
load_signals -> normalize -> profile_and_triage
  -> Parallel(score_relevance, assess_risk_llm, assess_risk_fast_path)
  -> merge_assessments
  -> Condition(has_signals)
        oui : Router(synthesis_router) -> llm_synthesis | deterministic_synthesis
        non : empty_digest
```

- Les données passent par le `session_state` Agno, via `run_context`. Les étapes parallèles écrivent chacune des clés différentes.
- Les agents sont injectés, ce qui permet de tester le workflow sans aucun appel LLM.

### Tri du risque ([agents/v2/triage.py](../agents/v2/triage.py))

- L'analyse de risque par LLM est réservée aux artefacts (dépôts GitHub, releases, modèles HF) et aux signaux qui portent un marqueur (sécurité, compatibilité, suspicion, injection, leurre).
- Les autres passent par un chemin rapide déterministe, qui applique les mêmes règles d'arbitrage.
- **Validation hors ligne** sur les runs sauvegardés (référence v4.1) : 50 % des appels LLM de risque sont évités, sur DEV comme sur TEST, avec **0 signal à risque manqué et 0 prédiction modifiée**.

### Synthèse hybride ([agents/v2/synthesis.py](../agents/v2/synthesis.py))

- L'ancien `SynthesisAgent` créait un agent Agno mais ne l'appelait jamais.
- Désormais, Python calcule tous les faits, et le LLM rédige le résumé, les « pourquoi c'est important » et les recommandations, avec un `output_schema` Pydantic.
- **Vérification** : les `signal_id` inconnus sont rejetés, et un résumé qui contient un nombre absent des faits calculés est remplacé.
- Le fallback est explicite (`synthesis.used_fallback` et sa raison).
- Le bug de formulation de v0 est corrigé : un risque HIGH n'est plus présenté comme « critical ».

### `main.py`

```powershell
.\.venv\Scripts\python.exe main.py                                  # v2, sources en direct
.\.venv\Scripts\python.exe main.py --agent-version v0               # comportement original
.\.venv\Scripts\python.exe main.py --frozen --split dev --max-signals 6
```

- Option `--agent-version v0|v2`, avec v2 par défaut. La source GitHub Releases fait partie de la collecte, et une source en panne n'arrête plus le pipeline.
- Le modèle de synthèse est `gpt-oss-20b`, pour ne pas consommer le quota du modèle de pertinence. Un quota épuisé produit un message clair (code de sortie 3).
- **Démonstration réelle** (6 signaux DEV, tous les rôles sur gpt-oss-20b) : 0 fallback, synthèse LLM vérifiée, recommandations rattachées à des signaux existants.
- **Tests** : 68 tests hors ligne réussis, dont 16 pour le bloc 3 ([tests/test_v2_pipeline.py](../tests/test_v2_pipeline.py)).

## 9. Application web locale

Une interface web qui tourne en local (elle remplace l'ancienne app Streamlit). Elle utilise uniquement Starlette et Uvicorn, déjà installés avec Agno : aucune installation supplémentaire n'est nécessaire.

```powershell
.\.venv\Scripts\python.exe -m webapp
```

L'application s'ouvre sur <http://127.0.0.1:8765> (option `--port`, et `--no-browser` pour ne pas ouvrir le navigateur).

| Page | Contenu |
|---|---|
| Accueil | Présentation, indicateurs avant/après (TEST), configuration LLM |
| Actualités | Fil des signaux évalués, classés par pertinence (analyses lancées depuis l'application, puis dataset de référence), avec une liste « À surveiller » pour les signaux à risque, qui restent aussi affichés dans le fil et marqués d'un liseré ; filtres par source, pertinence, origine et risque, recherche, et bouton « Actualiser depuis les sources » (collecte en direct puis analyse v2) |
| Analyse | Lance le vrai pipeline (v0 ou v2 ; dataset figé ou sources en direct) et affiche les étapes du workflow Agno en direct, le digest, les recommandations et un tableau des signaux |
| Benchmarks | Graphiques v0 / v2, DEV ou TEST, référence v4 ou v4.1, robustesse aux injections |
| Architecture | Schéma du workflow Agno (Step, Parallel, Condition, Router) et des couches de fiabilité |
| Explorateur | Les 72 signaux, avec l'annotation de référence face à la prédiction de v2 et un filtre sur les désaccords |

- Cliquer sur un signal ouvre un panneau de détail : rubric de pertinence, avis brut du LLM, preuves vérifiées, citations rejetées et ajustements déterministes.
- Chaque analyse lancée consomme le quota du fournisseur LLM. Le champ « Modèle » permet d'utiliser par exemple `openai/gpt-oss-20b` quand le quota de `gpt-oss-120b` est épuisé.
- Les analyses sont sauvegardées dans `results/app_runs/`.
- Code : [webapp/server.py](../webapp/server.py) et [webapp/static/](../webapp/static/). Tests : [tests/test_webapp.py](../tests/test_webapp.py).
