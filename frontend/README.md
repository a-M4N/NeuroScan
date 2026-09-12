# NeuroScan — Frontend

Clinical brain MRI diagnosis dashboard built with **React**, **Vite**, and **Tailwind CSS v4**.

For detailed architectural notes, component breakdowns, and API contracts, see [FRONTEND_BUILD_SUMMARY.md](../FRONTEND_BUILD_SUMMARY.md).

---

## Quick Start

### 1. Install Dependencies
```bash
pnpm install
```

### 2. Environment Configuration
Ensure `.env` exists with the backend API URL:
```ini
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Run Development Server
```bash
pnpm dev
```
Accessible at: `http://localhost:5173/`

### 4. Production Build & Lint
```bash
pnpm build
pnpm lint
```

---

## Tech Stack
* **Framework:** React 19
* **Build Tool:** Vite 8
* **Styling:** Tailwind CSS v4 via PostCSS
* **Routing:** React Router DOM v7
* **HTTP Client:** Axios
* **Charts:** Recharts (installed for analytics phase)
