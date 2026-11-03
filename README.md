# ShelfWise

Consumption-aware household inventory & waste-prevention app — built from the
Figma prototype and the ShelfWise brand sheet.

**Stack:** HTML + CSS + vanilla JS (frontend, no framework) · Python/Flask (backend) · MySQL (hosted)

---

## What's included

- Create account / sign in, household creation + invite codes
- Home dashboard (urgent/soon/safe counters, Use First scroller, High Waste Risk list)
- Inventory list with category filters and a live SVG waste-risk ring per item
- Add Item wizard (name/category → quantity/storage/expiry)
- Waste Risk Score engine (`backend/app/services/risk_engine.py`) — expiry proximity,
  quantity pressure, and a data-confidence penalty combine into a 0–100 score
- ShelfWise AI chat (Google Gemini-backed, with a graceful "not configured" fallback)
- Grocery Board — shared sticky notes, mark "Bought" to clear
- Analytics — waste %, savings, food-wasted-by-month and by-category charts (Chart.js)
- Use First / Don't Buy Yet / What-If Simulator tools
- Shopping List, Purchase History
- Settings: light/dark/system theme, language picker, notification toggles, household
  management, change password
- Floating voice assistant (Web Speech API) on every page — try "Add milk to my list"
- Full light + dark themes built from the brand palette, responsive down to mobile
  (sidebar becomes a slide-out drawer under 960px)
- Logo (`frontend/assets/logo-mark.png`) is the real cutout from the brand sheet with a
  transparent background, used in the sidebar and on the auth page in both themes

## API keys / secrets to fill in

All of these live in `backend/.env` (copy from `backend/.env.example`):

| Variable | Used for | Required? |
|---|---|---|
| `SECRET_KEY` | Flask session signing | Yes — set to any random string |
| `DATABASE_URL` | Full connection string for a hosted MySQL (PlanetScale, Railway, AWS RDS, Clever Cloud, etc.) | Use this **or** the four DB_* fields below |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | MySQL connection, field-by-field | Only used if `DATABASE_URL` is blank |
| `DB_SSL` / `DB_SSL_CA` | Enable SSL for hosts that require it (most hosted MySQL does) | Set `DB_SSL=true` if your host's docs say so |
| `GEMINI_API_KEY` | ShelfWise AI chat + recipe suggestions (Google Gemini) | No — chat degrades gracefully to a "not configured" message without it |
| `GEMINI_MODEL` | Which Gemini model the chat uses | No — defaults to `gemini-flash-latest` |

Get a free Gemini key at https://aistudio.google.com/apikey.

## Setup

### 1. Database (hosted)

Create a MySQL database with whatever provider you're using and grab its
connection string. Paste it into `DATABASE_URL` in `.env`:

```
DATABASE_URL=mysql+pymysql://user:password@your-host.example.com:3306/shelfwise
```

(If your provider gives you a `mysql://...` URL, that's fine as-is — the app
rewrites the scheme automatically.) If your provider requires SSL (most do),
also set `DB_SSL=true`.

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # then fill in DATABASE_URL / DB_SSL / GEMINI_API_KEY
python seed.py                 # creates tables (and the DB, if your user can) + a sample household
python run.py                  # starts the API on http://localhost:5000
```

Sample login after seeding: **mia@example.com / password123**

> Prefer an isolated environment? `python -m venv venv` then activate it
> (`source venv/bin/activate` / Windows: `venv\Scripts\activate`) before the
> `pip install` line — entirely optional, everything above works with a
> plain system Python install too.

### 3. Frontend

Any static file server works — the frontend calls the API at `http://localhost:5000`.

```bash
cd frontend
python -m http.server 5500
# open http://localhost:5500/auth.html
```

> **Login bounces back to `auth.html`?** Open the frontend and the API from the same
> hostname. Browsers treat `localhost` and `127.0.0.1` as different sites and drop the
> session cookie between them. `api.js` now follows the host you opened the page from
> (so VS Code Live Server's `127.0.0.1:5500` works), and the sign-in page tells you if the
> cookie was rejected instead of silently looping.

If you serve the frontend from a different port/origin, update `API_BASE` in
`frontend/js/api.js` and add your origin to the CORS list in `backend/app/__init__.py`.

## Project structure
```
shelfwise/
  backend/
    app/
      config.py              # builds the DB connection from DATABASE_URL or DB_* fields
      models.py               # Household, User, Item, ConsumptionLog, PurchaseHistory,
                              # ShoppingListItem, BoardNote, ChatMessage
      services/risk_engine.py
      routes/                 # auth, households, items, insights, shopping, board,
                              # analytics, chatbot, settings — one blueprint each
    schema.sql                # reference SQL (seed.py also creates tables via SQLAlchemy)
    seed.py
    run.py
  frontend/
    auth.html                 # create account / sign in
    app.html                  # SPA shell (sidebar + router)
    css/style.css             # full design system, light + dark
    js/
      api.js, app.js, theme.js, ring.js, voice.js
      pages/                  # home, inventory, additem, chat, board, analytics,
                              # tools, lists, settings — one module per screen
    assets/                   # logo-mark.png (transparent icon), logo-horizontal-light.png,
                              # favicon.png — all cut from the brand sheet
```

## Notes on the Waste Risk Score
Score = expiry proximity (0–70 pts, scaled to the category's typical shelf life) +
quantity pressure (0–20 pts, higher if there's more on hand than the household's
recent consumption rate can get through) + a 10-point penalty for items with no
real expiry date on file. ≥65 = High Risk (red), ≥40 = Expiring Soon (amber),
below = Safe (green) — matching the ring colors in the prototype.

## Deploying beyond localhost
This README covers running the backend and frontend locally against a hosted
database. If you later deploy the Flask API itself somewhere (Render, Railway,
Fly.io, etc.) rather than running it on your own machine:
1. Update `API_BASE` in `frontend/js/api.js` to your deployed API's URL.
2. Add your deployed frontend's origin to the `origins` list in
   `backend/app/__init__.py` (CORS).
3. Set all the same `.env` variables as environment variables on your hosting
   platform instead of a local `.env` file.


## Households & invites

- One account can belong to **several households** (e.g. "Home" and "Parents' house"). Use the
  household menu at the top of the sidebar to switch; each household has its own items, board,
  shopping list and chat.
- **Invite links** (Household page → *Invite someone*): personal, single-use, expire in 7 days.
  They are emailed if SMTP is configured, otherwise copy / WhatsApp / your email app.
- **Household code**: a reusable code owners can reset. Joining by code or link always shows
  which household it points to first.
- Existing databases are upgraded automatically the next time you run `python run.py`
  (adds the `household_members` and `invites` tables, never alters existing ones).
  `python migrate.py` does the same on demand.
- Tests: `cd backend && python tests/test_households.py` (uses a throwaway SQLite file).
