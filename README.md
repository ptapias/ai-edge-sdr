# AI Edge SDR

AI-powered Sales Development Representative for LinkedIn lead generation, qualification, and outreach automation.

## Quick Start

### 1. Backend Setup

```bash
cd webapp/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys:
# - ANTHROPIC_API_KEY (required for AI features)
# - MILLION_VERIFIER_API_KEY (optional, for email verification)

# Start server
uvicorn app.main:app --reload --port 8080
```

API docs available at: http://localhost:8080/docs

### 2. Frontend Setup

```bash
cd webapp/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend available at: http://localhost:3000

## Features

### Search Leads
- Natural language search: "CEOs at tech companies in Spain with 50+ employees"
- AI converts your query to structured Apify filters
- Leads stored in Supabase (PostgreSQL)

### Lead Management
- View, filter, and sort leads
- Bulk email verification via Million Verifier
- AI-powered lead scoring (hot/warm/cold)
- Generate personalized LinkedIn messages

### N8N Integration
- Trigger LinkedIn connection requests via N8N webhooks
- Sync lead status back to the webapp

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search/` | POST | Search leads with natural language |
| `/api/search/preview` | POST | Preview how query will be interpreted |
| `/api/leads/` | GET | List leads with pagination |
| `/api/leads/verify` | POST | Verify emails for leads |
| `/api/leads/qualify` | POST | Score leads with AI |
| `/api/leads/{id}/message/linkedin` | POST | Generate LinkedIn message |
| `/api/leads/{id}/action/linkedin` | POST | Trigger N8N connection |
| `/api/campaigns/` | GET/POST | Manage campaigns |
| `/api/business-profiles/` | GET/POST | Manage business profiles |

## Environment Variables

```bash
# Required
APIFY_API_TOKEN=apify_api_XXX
ANTHROPIC_API_KEY=sk-ant-XXX

# Optional
MILLION_VERIFIER_API_KEY=XXX
N8N_BASE_URL=http://localhost:5678
N8N_WEBHOOK_LINKEDIN=/webhook/linkedin-send
```

## Project Structure

```
webapp/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Settings
│   │   ├── database.py       # SQLite setup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   └── services/         # Business logic
│   ├── requirements.txt
│   └── .env
│
└── frontend/
    ├── src/
    │   ├── pages/            # React pages
    │   ├── services/         # API client
    │   └── App.tsx           # Main app
    ├── package.json
    └── vite.config.ts
```

## Tech Stack

- **Backend**: FastAPI + Supabase (PostgreSQL) + SQLAlchemy
- **Frontend**: React + Vite + TailwindCSS + React Query
- **AI**: Claude (Anthropic) for NL processing and lead scoring
- **Leads**: Apify Leads Finder
- **Email Verification**: Million Verifier
- **LinkedIn Automation**: Unipile API
