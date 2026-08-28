# SUPER NOVA RECOVERY

Outil WinPE hors ligne permettant de récupérer l’accès à un compte local Windows autorisé, sans envoyer de données sur Internet.

## Fonctionnalités

- écran de politique de confidentialité avec acceptation obligatoire avant l’analyse ;
- interface disponible en français et en anglais ;
- détection de toutes les installations Windows accessibles sur les volumes montés ;
- sélection explicite de la partition Windows à analyser ;
- détection des volumes BitLocker verrouillés et exclusion de ces volumes ;
- sauvegarde protégée des ruches système avant toute modification ;
- réinitialisation d’un compte local via un déclencheur IFEO à usage unique ;
- nettoyage automatique des fichiers temporaires et du déclencheur après l’opération ;
- indicateur animé pendant l’application des modifications.

## Architecture

```text
SUPER_NOVA_RECOVERY/
├── recovery.hta          Interface graphique et flux de récupération
├── recovery.bat          Ancienne méthode, conservée inactive et non copiée dans WinPE
├── assets/
│   └── SUPER_NOVA.ico    Icône de l’application
├── build/
│   ├── build_winpe.bat   Construction de l’image WinPE (ADK requis)
│   └── winpeshl.ini      Lancement automatique de recovery.hta
└── output/
    ├── SUPER_NOVA_RECOVERY.iso
    ├── SUPER_NOVA_RECOVERY.zip
    └── SHA256SUMS.txt
```

## Prérequis

Installer dans cet ordre :

1. **Windows ADK**, avec le composant **Deployment Tools** ;
2. **WinPE Add-on pour l’ADK**.

La construction doit être lancée dans **Deployment and Imaging Tools Environment** avec des droits administrateur.

Prévoir environ 10 Go d’espace libre.

## Fonctionnement

1. Démarrer sur l’ISO WinPE SUPER NOVA RECOVERY.
2. Lire et accepter la politique de confidentialité.
3. Lancer l’analyse des volumes et sélectionner l’installation Windows cible.
4. Sélectionner le compte local à récupérer et confirmer l’opération.
5. L’outil sauvegarde les ruches système, protège ses scripts et configure le déclencheur IFEO.
6. Redémarrer la machine, puis appuyer cinq fois sur **Maj** à l’écran de connexion.
7. Le script s’exécute sous SYSTEM, retire immédiatement le déclencheur et effectue la récupération.
8. Les fichiers temporaires et les sauvegardes sont supprimés lorsque le parcours est terminé.

Le compte Microsoft n’est pas réinitialisé localement : l’outil affiche le lien officiel de récupération Microsoft. La récupération des données peut toutefois être proposée selon le parcours choisi.

## BitLocker

- Un volume BitLocker verrouillé est détecté puis exclu de l’analyse.
- Il doit être déverrouillé avec sa clé de récupération avant de relancer l’opération.
- Un volume BitLocker déjà déverrouillé peut être analysé normalement.

## Limitations

| Cas | Comportement |
|-----|-------------|
| Compte local | Récupération prise en charge |
| Compte Microsoft (@outlook, @hotmail, etc.) | Réinitialisation locale impossible ; utiliser account.live.com |
| Compte Azure AD / Microsoft 365 | Non pris en charge ; contacter l’administrateur informatique |
| BitLocker verrouillé | Volume exclu jusqu’à déverrouillage |
| Plusieurs installations Windows | L’utilisateur choisit explicitement le volume cible |

## Construction

```bat
REM Ouvrir « Deployment and Imaging Tools Environment » en administrateur
cd build
build_winpe.bat
```

Les livrables sont créés dans `output/` :

- `SUPER_NOVA_RECOVERY.iso` : image bootable pour une machine virtuelle ou un lecteur optique ;
- `SUPER_NOVA_RECOVERY.zip` : contenu WinPE à extraire sur une clé USB FAT32 ;
- `SHA256SUMS.txt` : empreintes SHA-256 des deux livrables.

## Vérification d’intégrité

Dans PowerShell :

```powershell
Get-FileHash .\output\SUPER_NOVA_RECOVERY.iso -Algorithm SHA256
Get-FileHash .\output\SUPER_NOVA_RECOVERY.zip -Algorithm SHA256
Get-Content .\output\SHA256SUMS.txt
```

## Utilisation responsable

Utiliser cet outil uniquement sur une machine et des données pour lesquels vous disposez d’une autorisation. L’opération modifie le registre et certains fichiers système de l’installation Windows sélectionnée.
