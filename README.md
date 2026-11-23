# School – modules Odoo 18

Ensemble de modules Odoo 18 pour la gestion d'un établissement scolaire : admissions, élèves, notes, frais de scolarité et relances de factures impayées.

## Modules

| Module | Rôle | Dépend de |
|---|---|---|
| `school_business_backend` | Cœur métier : admissions, élèves, classes, matières, notes, bulletins | `base`, `mail`, `portal` |
| `school_business_frontend` | Formulaire d'admission public sur le site web | `school_business_backend`, `website` |
| `school_fees` | Frais de scolarité par niveau et facturation automatique des élèves | `school_business_backend`, `account` |
| `account_invoice_overdue_reminder` | Relances des factures clients impayées (module OCA) | `account` |

### `school_business_backend` (application)

- Demandes d'admission suivies par étapes : New, Application Submitted, Interview, Entrance Exam, Accepted, Enrolled, Refused.
- Planification des entretiens et des examens d'entrée, avec historique des échanges (e-mails, activités).
- Gestion des années scolaires (`school.year`) : année courante par société, ouverture et clôture.
- Niveaux, classes, matières, périodes et élèves.
- Notes, bulletins (rapport PDF) et export des notes.
- À l'inscription (« Enrolled ») : création du compte portail et de la fiche élève.

### `school_business_frontend`

- **Étape 1** : le visiteur renseigne l'élève, l'adresse, le parent/tuteur et la scolarité (niveau, année scolaire ouverte, école précédente).
- **Étape 2** : téléversement du document de candidature et soumission du dossier.
- Lien de modification sécurisé par jeton, envoyable par e-mail (bouton **Send Form Link**).
- Champ **Is a Student** (`is_student`) sur les contacts, coché automatiquement à l'inscription de l'élève.

| Route | Rôle |
|---|---|
| `/admission` | Redirige vers le formulaire |
| `/admission/apply` | Étape 1 : formulaire d'admission |
| `/admission/apply/submit` | Enregistrement de l'étape 1 |
| `/admission/<id>/edit` | Modification du dossier (jeton requis) |

### `school_fees`

- Frais de scolarité définis par niveau et par année scolaire.
- Génération automatique des factures des élèves (brouillons à vérifier puis valider), y compris par tâche planifiée.
- Choix du payeur (parent/tuteur) et du nombre d'échéances pour chaque élève.
- Suivi des factures depuis la fiche élève et relances de paiement.

### `account_invoice_overdue_reminder`

Module tiers de l'OCA (Akretion, licence AGPL-3, dépôt `OCA/credit-control`). Il n'est pas développé ici : ne pas le modifier sans nécessité, pour pouvoir le mettre à jour depuis la source.

## Installation

1. Ajouter le dossier `custom/school` au `addons_path` d'Odoo.
2. Mettre à jour la liste des applications.
3. Installer les modules voulus. Les dépendances s'installent automatiquement.

```
odoo-bin -d <base> -i school_business_backend,school_business_frontend,school_fees
```

Pour appliquer des modifications :

```
odoo-bin -d <base> -u school_business_backend,school_business_frontend,school_fees
```

## Configuration initiale

1. Créer au moins une année scolaire **ouverte** (`school.year`) et la définir comme année courante dans les paramètres. Le formulaire web n'affiche que les années ouvertes.
2. Vérifier les niveaux proposés (`school.level`).
3. Pour `school_fees` : définir les frais de chaque niveau, année par année.

## Licences

- `school_business_backend`, `school_business_frontend`, `school_fees` : LGPL-3
- `account_invoice_overdue_reminder` : AGPL-3
