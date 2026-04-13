# Rapport Qualite AgroX

- Date (UTC): 2026-04-13T14:55:30+00:00
- Algorithme: XGBoostClassifier
- Accuracy test: 0.9462809917355371
- Balanced accuracy: 0.9398151439744045
- F1 weighted: 0.9460256686758998
- F1 CV: 0.9149770343092728

## Resultats des 10 cas fixes

- Cas reussis: 9/10 (90.00%)

| Cas | Attendu | Obtenu | Confiance | Verdict |
|---|---|---|---:|---|
| Sol limono-argileux equilibre | favorable | favorable | 97.19% | OK |
| Sol degrade sec et carence N/P | non_favorable | non_favorable | 97.57% | OK |
| Exces potassium severe | non_favorable | non_favorable | 69.0% | OK |
| Hydromorphe | non_favorable | non_favorable | 96.58% | OK |
| Salin | non_favorable | non_favorable | 69.0% | OK |
| Calcaire tropical | non_favorable | non_favorable | 74.49% | OK |
| Organique humide tempere | favorable | favorable | 97.22% | OK |
| Argilo-limoneux bien equilibre | favorable | favorable | 97.22% | OK |
| Limono-sableux sec | non_favorable | non_favorable | 81.32% | OK |
| Argilo-sableux moyen | a_verifier | favorable | 89.72% | ECHEC |

## Details des motifs

- Sol limono-argileux equilibre: Décision alignée sur le modèle
- Sol degrade sec et carence N/P: Décision alignée sur le modèle
- Exces potassium severe: Déséquilibre NPK sévère détecté
- Hydromorphe: Sol hydromorphe : risque d'asphyxie racinaire
- Salin: Sol salin : contrainte sévère pour la plupart des cultures
- Calcaire tropical: Décision alignée sur le modèle
- Organique humide tempere: Décision alignée sur le modèle
- Argilo-limoneux bien equilibre: Décision alignée sur le modèle
- Limono-sableux sec: Décision alignée sur le modèle
- Argilo-sableux moyen: Décision alignée sur le modèle