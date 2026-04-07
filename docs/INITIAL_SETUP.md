# Αρχική Ρύθμιση - EllinCRM

Αυτός ο οδηγός περιγράφει τα βήματα που πρέπει να ακολουθήσετε **πριν** εκκινήσετε το project για πρώτη φορά.

---

## Γρήγορη Επισκόπηση

| Βήμα | Υποχρεωτικό | Χρόνος |
|------|-------------|--------|
| 1. Δημιουργία .env αρχείων | ✅ Ναι | 2 λεπτά |
| 2. Ρύθμιση Database URL | ✅ Ναι | 1 λεπτό |
| 3. HuggingFace Token | ❌ Προαιρετικό | 5 λεπτά |
| 4. Google Sheets Integration | ❌ Προαιρετικό | 15 λεπτά |

---

## Βήμα 1: Δημιουργία .env Αρχείων

### Backend

```bash
cd backend
cp .env.example .env
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
```

---


## Βήμα 2: Ρύθμιση Backend (.env)

Ανοίξτε το αρχείο `backend/.env` και ρυθμίστε τα παρακάτω:

### Υποχρεωτικές Ρυθμίσεις

#### Database URL

Το `.env.example` περιέχει ήδη τη σωστή τιμή για Docker:

```bash
DATABASE_URL=postgresql+asyncpg://ellincrm:ellincrm_dev_password@db:5432/ellincrm
```

**Αν τρέχετε με Docker (Συνιστάται):**

Αφήστε την default τιμή - είναι ήδη σωστή! Η τιμή `@db:5432` χρησιμοποιεί το Docker internal hostname.

**Αν τρέχετε χωρίς Docker (locally):**

Αλλάξτε το DATABASE_URL ανάλογα με το πού τρέχει η PostgreSQL:

```bash
# Backend local + Database σε Docker container
DATABASE_URL=postgresql+asyncpg://ellincrm:ellincrm_dev_password@localhost:7001/ellincrm

# Δική σας PostgreSQL locally
DATABASE_URL=postgresql+asyncpg://your_user:your_password@localhost:5432/your_database
```

| Scenario | Host | Port | Σημείωση |
|----------|------|------|----------|
| Full Docker | `db` | `5432` | Default στο .env.example ✓ |
| Backend local + DB Docker | `localhost` | `7001` | Αλλάξτε στο .env |
| Full local PostgreSQL | `localhost` | `5432` | Αλλάξτε στο .env |

---

### Προαιρετικές Ρυθμίσεις

#### HuggingFace Token (για AI Semantic Search)

Το σύστημα χρησιμοποιεί embedding models για semantic search. Υπάρχουν δύο επιλογές:

| Model | Token Required | Ποιότητα |
|-------|----------------|----------|
| `google/embeddinggemma-300m` | ✅ Ναι | Καλύτερη |
| `paraphrase-multilingual-mpnet-base-v2` | ❌ Όχι | Πολύ καλή |

**Χωρίς token:** Το σύστημα χρησιμοποιεί αυτόματα το fallback model. Λειτουργεί κανονικά!

**Με token (προαιρετικό):**
1. Δημιουργήστε λογαριασμό στο [HuggingFace](https://huggingface.co/)
2. Πάρτε token από: https://huggingface.co/settings/tokens
3. Αποδεχτείτε τους όρους του model: https://huggingface.co/google/embeddinggemma-300m
4. Προσθέστε στο `.env`:
   ```bash
   HUGGINGFACE_TOKEN=hf_your_token_here
   ```

#### Google Sheets Integration

Αν θέλετε να συγχρονίζετε δεδομένα στο Google Sheets, ακολουθήστε τον οδηγό:
📄 **[GOOGLE_SHEETS_SETUP.md](./GOOGLE_SHEETS_SETUP.md)**

Συνοπτικά:
```bash
# Path στο service account JSON
GOOGLE_CREDENTIALS_PATH=credentials/google-sheets-credentials.json

# ID του spreadsheet (από το URL)
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id-here
```

---

## Βήμα 3: Ρύθμιση Frontend (.env.local)

Ανοίξτε το αρχείο `frontend/.env.local`:

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:7000

# WebSocket URL για real-time notifications
NEXT_PUBLIC_WS_URL=ws://localhost:7000/ws/notifications
```

> **Σημείωση:** Οι default τιμές είναι σωστές για local development. Αλλάξτε μόνο αν χρησιμοποιείτε διαφορετικές πόρτες.

---

## Βήμα 4: Εκκίνηση

### Με Docker (Συνιστάται)

```bash
cd 

# Production mode
docker compose --profile prod up --build -d

# Development mode (με hot reload)
docker compose --profile dev up --build
```

### Χωρίς Docker

```bash
# Terminal 1: Database (χρειάζεστε PostgreSQL με pgvector)
# Εναλλακτικά, τρέξτε μόνο τη database σε Docker:
docker compose up db -d

# Terminal 2: Backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 7000 --reload

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

---

## Βήμα 5: Επαλήθευση

Μετά την εκκίνηση, επαληθεύστε ότι όλα λειτουργούν:

### Με Docker

| Service | URL | Αναμενόμενο |
|---------|-----|-------------|
| Frontend | http://localhost:7002 | Dashboard |
| Backend API | http://localhost:7000/docs | Swagger UI |
| Health Check | http://localhost:7000/health | `{"status": "healthy", ...}` |

### Χωρίς Docker (Local)

| Service | URL | Αναμενόμενο |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Dashboard |
| Backend API | http://localhost:7000/docs | Swagger UI |
| Health Check | http://localhost:7000/health | `{"status": "healthy", ...}` |

> **Σημείωση:** Η διαφορά είναι στο Frontend port: **7002** (Docker) vs **3000** (local)

---

## Συχνά Προβλήματα

### "Database connection refused"
- **Docker:** Βεβαιωθείτε ότι το `db` container τρέχει: `docker compose ps`
- **Local:** Βεβαιωθείτε ότι η PostgreSQL τρέχει και το DATABASE_URL είναι σωστό

### "Embedding model loading failed"
- Το σύστημα θα χρησιμοποιήσει αυτόματα το fallback model
- Αν θέλετε το primary model, ελέγξτε το HUGGINGFACE_TOKEN

### "Google Sheets permission denied"
- Βεβαιωθείτε ότι κοινοποιήσατε το spreadsheet με το Service Account email
- Δείτε: [GOOGLE_SHEETS_SETUP.md](./GOOGLE_SHEETS_SETUP.md)

---

## Δομή Αρχείων Configuration

```

├── backend/
│   ├── .env.example          # Template (στο git)
│   ├── .env                  # Οι ρυθμίσεις σας (gitignored)
│   └── credentials/
│       └── google-sheets-credentials.json  # Service account (gitignored)
│
└── frontend/
    ├── .env.example          # Template (στο git)
    └── .env.local            # Οι ρυθμίσεις σας (gitignored)
```

---

## Επόμενα Βήματα

Μετά την επιτυχή ρύθμιση:

1. 📖 Διαβάστε το [User Manual](./User_Manual.md) για οδηγίες χρήσης
2. 🎬 Δείτε το Demo Script στο `demo/DEMO_SCRIPT.md`
3. 🧪 Τρέξτε τα tests: `docker compose --profile test run --rm test`

---

**EllinCRM - Data Automation Platform**
