# DSS150P Weeks 2-3 Laboratory Package

Start with the Word laboratory guide. This repository is intentionally incomplete.

## Quick start
1. `python -m venv .venv`
2. Activate `.venv`
3. `pip install -r requirements.txt`
4. `docker compose up -d`
5. Load PostgreSQL seed: `docker exec -i dss150p-w23-postgres psql -U dss150p -d dss150p < sql/seed_support_tickets.sql`
6. Terminal A: `python src/local_api_server.py`
7. Terminal B: complete/run profiling and ingestion scripts.

Do not commit `.env`, generated raw data, or watermark state unless specifically instructed.

### AI Usage Disclosure
In the interest of transparency, this section discloses how AI tools were used in the development of this project. AI was used as a support tool for coding and analysis tasks, not as a replacement for human judgment, review, or decision-making.
The primary AI tools used in this project were Gemini and Claude, which assisted with code generation, debugging, code review, and analysis tasks.

