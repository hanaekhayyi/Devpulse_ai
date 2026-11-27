# SignalGuard — Historique complet et état actuel

**Date de mise à jour : 25 novembre 2026**

SignalGuard est une version améliorée de DevPulseAI, un pipeline multi-agents destiné à la veille technologique dans le domaine de l'intelligence artificielle et du machine learning.

L'objectif est de construire un système dont les décisions sont explicables, mesurables, reproductibles et résistantes aux erreurs des modèles LLM.

## 1. Objectif initial

Le projet a été choisi comme projet pratique pour comprendre puis améliorer une architecture multi-agents basée sur Agno.

Les objectifs étaient :

1. comprendre la responsabilité de chaque composant ;
2. exécuter et analyser la version originale ;
3. identifier ses limites ;
4. construire un dataset de référence ;
5. mesurer les performances avant et après les améliorations ;
6. améliorer progressivement la fiabilité du système.

## 2. Architecture originale

```text
Adapters → SignalCollector → RelevanceAgent → RiskAgent → SynthesisAgent
```

`SignalCollector` est un utilitaire Python déterministe. Il collecte, normalise, vérifie et déduplique les signaux grâce à la clé `source:id`.

`RelevanceAgent` attribue un score de pertinence compris entre 0 et 100.

`RiskAgent` analyse les vulnérabilités, les changements incompatibles, les dépréciations et les migrations.

`SynthesisAgent` regroupe les analyses et produit un digest. Dans l'état actuel, sa priorisation et son résumé restent principalement déterministes ; une synthèse LLM complète reste à développer.

## 3. Limites initiales identifiées

Les principales limites étaient :

| Limite | Conséquence |
|---|---|
| Score global peu explicable | Difficile de comprendre l'origine d'une note. |
| Absence de dataset stable | Comparaison des versions peu fiable. |
| Annotations insuffisamment structurées | Métriques potentiellement trompeuses. |
| Fallbacks peu visibles | Impossible de distinguer clairement LLM et heuristique. |
| Détection fragile des breaking changes | Faux positifs et faux négatifs. |
| Risques et suspicions mélangés | Suspicion parfois traitée comme menace confirmée. |
| Pipeline séquentiel | Appels LLM potentiellement coûteux. |

## 4. Configuration OpenRouter

La configuration LLM a été migrée vers une API compatible OpenAI via OpenRouter.

Les paramètres sont chargés par [config.py](../config.py) :

```text
OPENROUTER_API_KEY
OPENROUTER_BASE_URL
MODEL_RELEVANCE
MODEL_RISK
MODEL_SYNTHESIS
```

Le modèle utilisé pour les benchmarks est :

```text
mistralai/mistral-small-3.2-24b-instruct
```

Les agents utilisent `OpenAIChat` avec l'URL OpenRouter.

## 5. Première exécution

La première exécution de `main.py` a confirmé que le pipeline fonctionnait avec environ 32 signaux provenant de plusieurs sources.

Cette exécution a démontré le fonctionnement technique du pipeline, mais elle ne permettait pas encore de savoir si les décisions étaient correctes. Un score produit par un LLM ne constitue pas automatiquement une vérité de référence.

## 6. Fallbacks explicites

Les agents enregistrent désormais explicitement l'état de dégradation :

```json
{
  "used_fallback": false,
  "fallback_reason": null
}
```

Le pipeline compte les fallbacks de pertinence et de risque. Les benchmarks réussis affichent actuellement un taux de fallback nul.

## 7. Dataset figé et GitHub Releases

Un dataset enrichi de 72 signaux a été construit :

| Source | Nombre |
|---|---:|
| GitHub trending | 12 |
| ArXiv | 12 |
| Hacker News | 12 |
| Medium | 12 |
| Hugging Face | 12 |
| GitHub Releases | 12 |
| **Total** | **72** |

La source GitHub Releases a été ajoutée dans [adapters/github_releases.py](../adapters/github_releases.py). Elle fournit des notes de version contenant des informations sur les migrations, les dépréciations, les changements d'API et le support des versions Python.

Le fichier central est [signals_frozen.json](../data/benchmark/signals_frozen.json). La collecte et la validation sont gérées par [freeze_signals.py](../scripts/freeze_signals.py).

## 8. Séparation DEV / TEST

```text
DEV  : 48 signaux
TEST : 24 signaux
```

DEV sert à analyser les erreurs et améliorer les agents. TEST sert à vérifier que les améliorations fonctionnent sur des signaux qui n'ont pas guidé leur développement.

Les annotations utilisées sont :

- [dev_gold_annotated_v4.json](../data/benchmark/dev_gold_annotated_v4.json)
- [test_gold_annotated_v4.json](../data/benchmark/test_gold_annotated_v4.json)

## 9. Annotations de référence v4

Les fichiers gold contiennent des annotations de référence préparées automatiquement puis vérifiées et corrigées dans le cadre du projet. Il est donc plus exact de parler d'annotations de référence vérifiées que d'annotations entièrement humaines.

Chaque annotation contient notamment :

```json
{
  "signal_id": "...",
  "relevance_score": 35,
  "risk_level": "MEDIUM",
  "risk_category": "COMPATIBILITY",
  "breaking_changes": true,
  "evidence": "...",
  "annotation_status": "verified"
}
```

La taxonomie v4 distingue `NONE`, `SECURITY`, `COMPATIBILITY` et `SUSPICION`.

L'audit est réalisé par [audit_gold_v4.py](../scripts/audit_gold_v4.py), avec le résultat dans [gold_v4_audit.json](../results/gold_v4_audit.json).

Les benchmarks enregistrent aussi les empreintes SHA-256 des fichiers utilisés.

## 10. Système de benchmark

Le dossier [benchmarks](../benchmarks) permet de :

1. charger les signaux figés ;
2. charger les annotations ;
3. exécuter les agents ;
4. associer les prédictions grâce au `signal_id` ;
5. calculer les métriques ;
6. sauvegarder les résultats et la latence.

Les métriques de pertinence sont : MAE, Spearman, NDCG@10 et Top-10 overlap.

Les métriques de risque sont : accuracy, précision, rappel, F1, Macro-F1, matrice de confusion, F1 des breaking changes, exactitude des catégories, fallbacks et latence.

NDCG@10 utilise maintenant des gains gradués normalisés sur l'échelle 0–100. Le Macro-F1 est rapporté à la fois pour les classes observées et pour toutes les classes déclarées, avec les classes sans support signalées séparément.

## 11. Baseline DevPulseAI v0

La baseline v0 a été recalculée sur le référentiel v4.

Résultats DEV :

| Métrique | Résultat |
|---|---:|
| MAE | 25,83 |
| Spearman | 0,680 |
| NDCG@10 normalisé | 0,770 |
| Accuracy risque | 0,854 |
| Breaking changes F1 | 1,000 |

Résultat : `baseline_v0_v4_recomputed_dev.json`.

## 12. SignalGuard v1

Les agents expérimentaux sont :

- `relevance_agent_v1.py`
- `risk_agent_v1.py`

### RelevanceAgentV1

Le score global est décomposé en quatre critères :

| Critère | Maximum |
|---|---:|
| Novelty | 25 |
| Technical relevance | 30 |
| Applicability | 25 |
| Timeliness | 20 |
| **Total** | **100** |

La validation Python vérifie les limites de chaque critère et la cohérence du total.

### RiskAgentV1

La sortie distingue le niveau de risque, la catégorie, les préoccupations, les preuves et les breaking changes.

Résultats DEV v1 sur v4 :

| Métrique | Résultat |
|---|---:|
| MAE | 21,98 |
| Spearman | 0,647 |
| NDCG@10 | 0,657 |
| Accuracy risque | 0,688 |
| Breaking changes F1 | 0,000 |

La MAE s'est améliorée, mais les deux breaking changes positifs du DEV n'ont pas été détectés.

## 13. SignalGuard v1.1

La version v1.1 est implémentée dans `risk_agent_v1_1.py`.

Elle conserve l'analyse du LLM puis applique une validation déterministe :

- détection des marqueurs explicites de compatibilité ;
- gestion des négations ;
- distinction entre preuve et indice ;
- filtrage des suspicions non justifiées ;
- ajout de `evidence_strength` avec `CONFIRMED`, `INDICATOR` ou `NONE`.

### Résultats DEV v1.1

| Métrique | Résultat |
|---|---:|
| MAE | 23,02 |
| Spearman | 0,498 |
| NDCG@10 | 0,657 |
| Accuracy risque | 0,813 |
| Catégorie de risque | 0,792 |
| Breaking changes F1 | 1,000 |
| Fallback rate | 0 % |

### Résultats TEST v1.1

| Métrique | Résultat |
|---|---:|
| MAE | 17,50 |
| Spearman | 0,549 |
| NDCG@10 | 0,709 |
| Top-10 overlap | 0,60 |
| Accuracy risque | 0,875 |
| Catégorie de risque | 0,750 |
| Breaking changes F1 | 1,000 |
| Fallback rate | 0 % |

Résultats :

- `baseline_v1_1_dev_final.json`
- `baseline_v1_1_test_final.json`

Les résultats montrent une détection robuste des breaking changes. Le rubric de pertinence reste néanmoins variable entre les exécutions LLM.

## 14. Post-validation offline

`revalidate_saved_risk.py` permet d'appliquer les règles déterministes à des prédictions sauvegardées sans nouvel appel LLM.

Cette procédure sert à isoler l'effet de la validation et ne constitue pas une nouvelle inférence.

Le résultat offline contient notamment :

- `api_calls_requested = 0` ;
- le fichier source ;
- la version des règles ;
- la durée réelle du post-traitement ;
- la date de validation ;
- la durée originale de l'exécution LLM.

## 15. Tests réalisés

Les tests couvrent la normalisation GitHub Releases, les réponses JSON, les fallbacks, les breaking changes positifs, les négations, les cas ambigus, les suspicions non justifiées et NDCG.

Commande :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Résultat actuel : **10 tests réussis**.

## 16. État réel de l'architecture

Les composants expérimentés sont :

```text
Collecte multi-sources
        ↓
SignalCollector
        ↓
RelevanceAgent / RelevanceAgentV1
        ↓
RiskAgent / RiskAgentV1.1
        ↓
Benchmark et validation déterministe
```

La version actuelle de [main.py](../main.py) utilise encore les agents originaux `RelevanceAgent` et `RiskAgent`. Les agents v1 et v1.1 sont principalement utilisés dans le benchmark et ne sont pas encore le comportement par défaut de l'application principale.

## 17. Améliorations restantes

Les points suivants restent à réaliser ou à approfondir :

### Structured Outputs Pydantic

Les réponses sont encore des dictionnaires validés manuellement. Les schémas Pydantic restent à ajouter.

### SynthesisAgent réellement piloté par le LLM

La synthèse actuelle est principalement déterministe. Une génération LLM contrôlée, avec vérification des identifiants de signaux, reste à développer.

### Reliability layer complet

Les fallbacks sont explicites, mais il reste à ajouter les retries, le backoff, la journalisation structurée et une gestion plus fine des erreurs réseau.

### Workflow Agno

Un workflow avec `Steps`, `Router`, `Condition` et état partagé reste à développer.

### Optimisation

Le cache, le routage adaptatif, la concurrence bornée, la réduction des tokens et le suivi du coût restent à étudier.

### Intégration principale

Après stabilisation, `main.py` devra permettre de sélectionner explicitement `v0`, `v1` ou `v1.1` sans supprimer immédiatement les anciennes versions.

## 18. Prochaines étapes recommandées

1. conserver v0, v1 et v1.1 comme références expérimentales ;
2. auditer les labels v4 encore ambigus ;
3. améliorer le rappel de la classe `MEDIUM` ;
4. calibrer séparément `RelevanceAgentV1` ;
5. ajouter les sorties Pydantic ;
6. intégrer v1.1 dans `main.py` avec sélection de version ;
7. améliorer `SynthesisAgent` ;
8. ajouter retries, backoff et journalisation ;
9. construire progressivement le workflow Agno ;
10. créer un nouveau jeu TEST indépendant pour l'évaluation finale.

## Conclusion

SignalGuard a évolué d'une démonstration multi-agents fonctionnelle vers une base expérimentale mesurable.

Les améliorations effectivement réalisées concernent la configuration OpenRouter, les fallbacks explicites, la collecte GitHub Releases, le dataset figé de 72 signaux, les annotations v4, le benchmark DEV/TEST, le rubric de pertinence, l'analyse evidence-based des risques, la détection déterministe des breaking changes, la traçabilité offline et les tests de non-régression.

Les travaux restants concernent principalement l'intégration finale dans `main.py`, les sorties Pydantic, la synthèse LLM, l'orchestration Agno et l'optimisation des appels.

Le projet possède désormais les fondations nécessaires pour mesurer et démontrer les améliorations apportées à DevPulseAI, sans prétendre encore être une version de production complète.
