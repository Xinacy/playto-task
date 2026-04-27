# Playto Task

This project has a Django REST backend and a Vite React frontend.

I could not host the project, but it is pretty easy to run locally. The backend works through Docker, and the frontend runs with Bun.

## Setup

### Backend

From the repository root:

```bash
docker compose up --build -d
```

Docker starts Postgres, Redis, the Django API, Celery worker, and Celery beat. It also runs migrations and seeds the demo data automatically when the backend container starts.

Backend API: `http://localhost:8000`

### Frontend

In another terminal:

```bash
cd frontend
bun i; bun dev
```

Frontend app: `http://localhost:5173`

That is it.
