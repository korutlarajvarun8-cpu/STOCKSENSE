# StockSense 📦

StockSense is an AI-powered, real-time inventory management system designed to streamline warehouse operations, track stock movements, and predict demand using advanced analytics.

## 🚀 Tech Stack

- **Backend:** FastAPI, Python, SQLAlchemy (Async), Redis, Alembic
- **Database:** MySQL
- **Frontend:** Next.js 14, React, Tailwind CSS, shadcn/ui
- **AI Integration:** OpenAI GPT (for the AI Inventory Assistant)

## ✨ Key Features

- **Real-Time Dashboard:** View stock alerts, recent activity, and demand forecasts.
- **Inventory Tracking:** Manage batches, serial numbers, and dynamic reorder rules.
- **Operations Management:** Seamlessly handle Purchase Orders, Sales Orders, Receipts, Deliveries, Transfers, and Adjustments.
- **AI Assistant:** A built-in chat interface that understands your inventory context to answer operational questions.
- **Real-time Updates:** WebSockets power instant UI updates when stock changes.

---

## 🛠️ Getting Started (Local Development)

### 1. Database Setup
StockSense requires **MySQL** and **Redis**. Ensure both are running locally.
- MySQL default port: `3306`
- Redis default port: `6379`

Create the database in MySQL:
```sql
CREATE DATABASE stocksense;
```

### 2. Backend Setup
Navigate to the `backend` directory and set up the Python environment.

```bash
cd backend
python -m venv .venv

# Activate the virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Configuration:**
Copy the example environment file and update your credentials:
```bash
cp ../.env.example ../.env
```
Ensure your `DATABASE_URL` in the `.env` file points to your local MySQL instance.

**Run Migrations:**
```bash
alembic upgrade head
```

**Start the Backend Server:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API documentation will be available at `http://localhost:8000/api/docs`.

---

### 3. Frontend Setup
Navigate to the `frontend` directory.

```bash
cd frontend

# Install Node modules
npm install

# Start the Next.js development server
npm run dev
```
The frontend will be available at `http://localhost:3000`.

---

## 📁 Repository Structure

- `/backend`: The FastAPI application, Alembic database migrations, and core business logic (Inventory Service).
- `/frontend`: The Next.js React application, UI components, and client-side logic.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
