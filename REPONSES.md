# TP CI/CD – GitHub Actions pour Airflow : réponses

Dépôt : `airflow-intro` · Airflow 3.1.0 · Python 3.12

## Partie 1 : mettre le projet sur GitHub

- **À quoi sert `git status` avant le commit ?** Il montre ce qui va partir dans le commit : les fichiers ajoutés, modifiés ou non suivis. On repère ainsi un fichier de trop (logs, secrets) avant qu'il entre dans l'historique, où il est difficile à effacer.
- **Que serait-il parti sans `.gitignore` ?** Les logs générés par Airflow (`logs/`), les caches Python (`__pycache__/`, `*.pyc`, `.pytest_cache/`), l'environnement virtuel `.venv/` et le fichier `.env`, qui contient souvent des secrets.

## Partie 2 : premier workflow

- **Sans `actions/checkout@v4` :** le runner démarre vide. `ls dags/` échoue (`No such file or directory`) et le job passe au rouge, parce que le code du dépôt n'a jamais été copié sur la machine.
- **Indentation YAML fausse :** comme en Python, la structure change ou devient invalide. GitHub affiche « Invalid workflow file » et le workflow ne se lance pas.

## Partie 3 : flake8

- **F401** : module importé mais jamais utilisé (non bloquant).
- **F821** : nom non défini, par exemple une variable ou une classe utilisée sans import. C'est bloquant, car le code plante à l'exécution (`NameError`).

## Partie 4 : pytest

- **`needs: lint` :** `test-dags` ne démarre que si `lint` est vert. Si le lint échoue, `test-dags` est sauté (*skipped*), ce qui évite 3 minutes d'installation inutile.
- **Le fichier de constraints :** il fige la version de chaque dépendance d'Airflow, avec une combinaison testée par l'équipe Airflow. Sans lui, pip installe les dernières versions disponibles, au risque d'incompatibilités et d'une CI qui casse sans changement de notre côté.
- **Le provider Postgres dans la CI :** le runner n'utilise pas l'image Docker. C'est une machine Ubuntu vide qui ne contient que ce qu'on y installe. Sans le provider, l'import de `PostgresHook` échoue.

## Partie 5 : casser un DAG

| Cas | Modification | Job qui échoue | Message à retrouver |
|-----|--------------|----------------|---------------------|
| A | Suppression de l'import de `PostgresHook` | `lint`, étape « Erreurs bloquantes » (`test-dags` est *skipped*) | `F821 undefined name 'PostgresHook'` |
| B | Suppression de l'appel `user_processing()` | `test-dags`, étape « Tester les DAGs » (`lint` est vert) | `AssertionError: assert 'user_processing' in {}` puis `KeyError: 'user_processing'` (2 failed, 1 passed) |
| C | Renommage de `store_user` en `save_user` | `test-dags`, étape « Tester les DAGs » (`lint` est vert) | `AssertionError: Tâches manquantes : {'store_user'}, en trop : {'save_user'}` (1 failed, 2 passed) |

- **Cas B, pourquoi flake8 ne voit rien ?** flake8 lit le code sans l'exécuter. Le fichier est syntaxiquement correct et tous les noms sont définis. Le problème est que la fonction décorée par `@dag` n'est jamais appelée, donc aucun objet DAG n'est créé. On ne le voit qu'en chargeant le fichier, ce que fait le DagBag.
- **Cas C, pourquoi faire échouer le test si le DAG fonctionne ?** Le `task_id` est un contrat. L'historique des exécutions, les XCom lus par `task_id`, les capteurs d'autres DAGs (`ExternalTaskSensor`) et le monitoring en dépendent. Le test oblige à faire ce changement volontairement, en mettant le test à jour, et non par accident.
- **Combien de temps pour trouver le cas B dans l'interface ?** Longtemps : il n'y a aucune erreur d'import, le DAG disparaît simplement de la liste. Il faut attendre le rescan du dossier (plusieurs minutes), puis chercher pourquoi le DAG manque. La CI donne la réponse en environ 3 minutes, avec le nom du DAG manquant.

## Pour aller plus loin : pull request

- **Le binôme peut-il valider à ma place ?** Sur GitHub, l'auteur d'une pull request ne peut pas l'approuver lui-même : il faut un autre relecteur. Le binôme peut approuver s'il a les droits, mais l'approbation n'a de valeur que s'il a vraiment relu le code.
- **Pourquoi une relecture humaine en plus de la CI ?** La CI vérifie seulement ce qu'on lui a appris à vérifier. Un humain juge la logique métier, la lisibilité, les choix de conception, la sécurité (secret en dur, requête dangereuse) et les cas que les tests ne couvrent pas. La relecture partage aussi la connaissance du code dans l'équipe.

## Bilan

1. **Deux erreurs que cette CI aurait détectées :** un import oublié ou mal écrit (provider absent, nom non défini, détecté par flake8 ou par le test d'import), et un DAG qui n'apparaît pas dans l'interface parce que la fonction `@dag` n'est pas appelée en bas du fichier (détecté par `test_user_processing_existe`).
2. **Pourquoi le lint avant les tests :** le lint prend quelques secondes, alors que les tests demandent environ 3 minutes d'installation d'Airflow. On échoue vite et à moindre coût sur les erreurs simples, et on ne lance les tests coûteux que sur un code déjà propre.
3. **En MLOps, la CI pourrait aussi vérifier :** que le modèle se charge et répond à une prédiction de test, que ses métriques (accuracy, F1, RMSE…) dépassent un seuil ou ne régressent pas par rapport au modèle en production, le schéma et la qualité des données d'entrée, la dérive des données, ainsi que la taille et la latence d'inférence du modèle.
