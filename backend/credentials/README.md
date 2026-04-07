# Google Sheets Credentials

Αυτός ο φάκελος περιέχει τα credentials για τη σύνδεση με Google Sheets.

---

## Οδηγίες Ρύθμισης

### 1. Δημιουργία Google Cloud Project
- Μεταβείτε στο [Google Cloud Console](https://console.cloud.google.com/)
- Δημιουργήστε νέο project ή επιλέξτε υπάρχον

### 2. Ενεργοποίηση APIs
- Πηγαίνετε στο **APIs & Services > Library**
- Αναζητήστε και ενεργοποιήστε: **Google Sheets API**
- Αναζητήστε και ενεργοποιήστε: **Google Drive API**

### 3. Δημιουργία Service Account
- Πηγαίνετε στο **APIs & Services > Credentials**
- Κλικ **"Create Credentials" > "Service Account"**
- Όνομα: `ellincrm-sheets-service`
- Κλικ **"Create and Continue" > "Done"**

### 4. Λήψη JSON Credentials
- Κλικ στο service account που δημιουργήσατε
- Καρτέλα **"Keys"**
- Κλικ **"Add Key" > "Create new key"**
- Επιλέξτε **JSON**
- Το αρχείο θα κατέβει αυτόματα

### 5. Τοποθέτηση Αρχείου
- Μετονομάστε το αρχείο σε `google-sheets-credentials.json`
- Τοποθετήστε το σε αυτόν τον φάκελο

---

## Δομή Φακέλου

```
credentials/
├── .gitignore                              # Αγνοεί τα πραγματικά credentials
├── README.md                               # Αυτό το αρχείο
├── google-sheets-credentials.example.json  # Παράδειγμα μορφής
└── google-sheets-credentials.json          # ΤΑ ΔΙΚΑ ΣΑΣ CREDENTIALS (δεν ανεβαίνει)
```

---

## Σημείωση Ασφαλείας

⚠️ **ΠΟΤΕ** μην κάνετε commit πραγματικά credentials στο Git!

Το `.gitignore` διασφαλίζει ότι το `google-sheets-credentials.json` δεν ανεβαίνει.

---

## Αντιμετώπιση Προβλημάτων

| Σφάλμα | Λύση |
|--------|------|
| **"Credentials not found"** | Βεβαιωθείτε ότι το αρχείο ονομάζεται ακριβώς `google-sheets-credentials.json` |
| **"Permission denied"** | Κοινοποιήστε το spreadsheet σας με το email του service account (βρίσκεται στο JSON ως `client_email`) |
| **"API not enabled"** | Ενεργοποιήστε και τα δύο APIs (Sheets + Drive) |
