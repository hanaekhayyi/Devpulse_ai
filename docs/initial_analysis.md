# Analyse de l’existant et plan d’amélioration SignalGuard

Ce document transforme les observations de l’audit de l’implémentation actuelle en un plan d’amélioration traçable.

## Tableau de suivi

| ID | Problème constaté | Amélioration SignalGuard | Comment mesurer le résultat ? |
|---|---|---|---|
| SG-01 | Scoring global peu explicable | Mettre en place un rubric-based scoring structuré, avec des critères explicites et éventuellement pondérés. | Corrélation entre les scores produits et des annotations humaines. |
| SG-02 | Classification des risques peu vérifiable | Produire des justifications structurées et vérifier que les éléments cités sont présents dans les signaux disponibles. | Macro-F1 et rappel des risques élevés. |
| SG-03 | Synthèse uniquement déterministe | Mettre en place une synthèse hybride combinant le classement Python et la génération de texte par le LLM. | Exactitude factuelle et qualité du rapport produit. |
| SG-04 | JSON sans validation stricte | Utiliser Pydantic pour définir les schémas et valider les sorties des agents. | Taux de sorties valides et nombre d’erreurs de validation. |
| SG-05 | Fallback détecté par chaîne de caractères | Ajouter des états de dégradation explicites, par exemple `used_fallback` et `fallback_reason`. | Taux de dégradation correctement signalé. |
| SG-06 | Tests limités | Ajouter des tests unitaires, d’intégration et, lorsque pertinent, des tests end-to-end. | Couverture des scénarios et taux de réussite des tests. |
| SG-07 | Appels LLM séquentiels | Étudier un routage adaptatif, un cache et une concurrence bornée, dans les limites du périmètre et des quotas. | Nombre d’appels par signal, latence moyenne et coût estimé. |
| SG-08 | Pipeline principalement séquentiel en Python | Évaluer un workflow Agno avec des nœuds de routage et de condition. | Traçabilité, branches exécutées et taux de complétion. |

## Périmètre prioritaire de la première phase

Pour une première itération courte, les éléments prioritaires sont :

1. Les schémas Pydantic et la validation des sorties (`SG-04`).
2. Les états de fallback explicites (`SG-05`).
3. L’utilisation réelle de `agent.run()` dans `SynthesisAgent` avec un fallback Python (`SG-03`).
4. Les tests des réponses valides, erreurs LLM, JSON invalides et erreurs réseau (`SG-06`).
5. La mise à jour de la documentation et des critères de mesure.

Les optimisations de performance et la refonte du workflow Agno pourront être traitées dans une phase ultérieure après stabilisation du comportement fonctionnel.
