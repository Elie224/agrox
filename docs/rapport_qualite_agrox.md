# Rapport Qualite AgroX

- Date (UTC): 2026-04-13T21:49:37+00:00
- Algorithme: XGBoostClassifier
- Accuracy test: 0.9462809917355371
- Balanced accuracy: 0.9466405972271597
- F1 weighted: 0.9464092583500104
- F1 CV: 0.8913518745408041

## Resultats des 10 cas fixes

- Cas reussis: 10/10 (100.00%)

| Cas | Attendu | Obtenu | Confiance | Verdict |
|---|---|---|---:|---|
| Sol limono-argileux equilibre | favorable | favorable | 99.81% | OK |
| Sol degrade sec et carence N/P | non_favorable | non_favorable | 97.83% | OK |
| Exces potassium severe | non_favorable | non_favorable | 69.0% | OK |
| Hydromorphe | non_favorable | non_favorable | 74.76% | OK |
| Salin | non_favorable | non_favorable | 69.0% | OK |
| Calcaire tropical | non_favorable | non_favorable | 90.57% | OK |
| Organique humide tempere | favorable | favorable | 99.81% | OK |
| Argilo-limoneux bien equilibre | favorable | favorable | 99.81% | OK |
| Limono-sableux sec | non_favorable | non_favorable | 85.88% | OK |
| Argilo-sableux moyen | a_verifier | a_verifier | 69.0% | OK |

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
- Argilo-sableux moyen: Mode responsable active: verification humaine requise