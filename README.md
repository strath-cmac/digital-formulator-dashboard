# Digital Formulator Dashboard

A **Streamlit-based web dashboard** that provides a comprehensive GUI for the [Digital Formulator API](https://github.com/strath-cmac/digital-formulator) — an AI-powered in-silico tablet formulation platform built on a physics-informed system of machine-learning models.

The dashboard is a **separate microservice** that communicates with the FastAPI backend over HTTP.  It is packaged as an independent Docker image and can be deployed alongside the API on any machine.

---

## Overview

The Digital Formulator system predicts tablet and blend properties from raw material (excipient) data, and optimises formulations to meet user-defined objectives and constraints.  This dashboard exposes three simulation tools through an interactive browser UI:

| Tool | Description |
|------|-------------|
| **Single Run** | Simulate granular and tablet properties at a fixed compaction pressure |
| **Multiple Run** | Generate compressibility and tensile-strength profiles across a CP range using Kawakita and Duckworth empirical models |
| **Digital Formulator** | Run NSGA-II (multi-objective) or mixed-variable GA (single-objective) to find Pareto-optimal formulations |

---

## Architecture

```
┌──────────────────────────────────┐      ┌────────────────────────────────────┐
│  Digital Formulator API          │      │  This Dashboard                    │
│  FastAPI · Port 8080             │◄─────│  Streamlit · Port 8501             │
│  github.com/strath-cmac/         │ HTTP │  github.com/strath-cmac/           │
│    digital-formulator            │      │    digital-formulator-dashboard     │
└──────────────────────────────────┘      └────────────────────────────────────┘
            Both services share a Docker bridge network (dm2_net)
```

---

## Pages

### 🏠 Home (Landing Page)
- Live API health check with one-click refresh
- Summary metrics: number of available excipients, objectives, and constraint types
- Reference tables for all valid excipient IDs, objective keys, constraint keys, and current API defaults

### 🔬 Single Run
- Select any combination of excipients with adjustable weight fractions (auto-normalised)
- Set compaction pressure (50 – 450 MPa)
- Output tabs:
  - **Granular Properties** — true/bulk/tapped density, Carr's Index, Hausner Ratio, FFC, EAOIF, flow classification
  - **Tablet Properties** — porosity and tensile strength (mean ± std)
  - **Morphology** — particle size distribution, aspect ratio distribution, PCA scores
  - **Formulation** — donut composition chart + fraction table
  - **Raw Data** — full JSON + download button

### 📈 Multiple Run
- Configure CP range and number of evaluation points
- Fits Kawakita (porosity) and Duckworth (tensile strength) empirical models
- Output tabs:
  - **Compressibility** — porosity vs. CP with 95 % confidence band
  - **Tensile Strength** — tensile strength vs. CP with 95 % confidence band
  - **Empirical Models** — fitted equation parameters with LaTeX rendering
  - **Granular Props** — properties at the first CP point
  - **Raw Data** — downloadable CSV profile + full JSON

### 🚀 Digital Formulator
- Full optimisation configuration surface:
  - API / drug loading (required)
  - Objective selection (1 obj → GA, 2+ obj → NSGA-II Pareto front)
  - Dynamic constraint builder (add / remove / adjust thresholds)
  - Fixed excipient settings (disintegrant, lubricant)
  - Filler search space and CP bounds
  - Solver settings (population size, iterations, threads, seed)
- Estimated runtime displayed before launch
- Output tabs:
  - Optimal formulation donut chart + component table
  - Granular and tablet KPIs
  - Morphology / PCA plots
  - Raw JSON + download

---

## Project Structure

```
digital-formulator-dashboard/
├── .github/
│   └── workflows/
│       └── docker-publish.yml   # CI: build & push Docker image on push to main
├── .streamlit/
│   └── config.toml              # Dark navy theme, CSRF protection
├── .env.example                 # API_BASE_URL template
├── Dockerfile                   # python:3.11-slim, port 8501
├── requirements.txt             # streamlit, requests, pandas, plotly, python-dotenv
├── app.py                       # Landing page
├── pages/
│   ├── 1_Single_Run.py
│   ├── 2_Multiple_Run.py
│   └── 3_Digital_Formulator.py
└── utils/
    ├── api_client.py            # All HTTP calls to the FastAPI backend
    └── plotting.py              # Plotly figure factories
```

---

## Quick Start — Docker Compose (Recommended)

The easiest way to run both the API and the dashboard together is with the provided `docker-compose.yml` (located one level above this folder, in the `Mohammad/` directory).

```bash
# 1. Build the API image (from the DM2-System-of-Models directory)
docker build -t dm2-api:latest ./DM2-System-of-Models

# 2. Build the dashboard image
docker build -t dm2-dashboard:latest ./digital-formulator-dashboard

# 3. Start both services
docker-compose up -d

# Dashboard:  http://<machine-ip>:8501
# API docs:   http://<machine-ip>:8080/docs
```

The `docker-compose.yml` creates a shared `dm2_net` bridge network so the dashboard reaches the API at `http://dm2_api:8080` (by service name, not `localhost`).

---

## Quick Start — Dashboard Only (Development)

```bash
# 1. Clone
git clone https://github.com/strath-cmac/digital-formulator-dashboard.git
cd digital-formulator-dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API URL
cp .env.example .env
# Edit .env: set API_BASE_URL=http://localhost:8080

# 4. Run
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Configuration

The dashboard is configured entirely through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8080` | Base URL of the Digital Formulator FastAPI backend |

In Docker Compose deployments, `API_BASE_URL` is automatically set to `http://dm2_api:8080` via the compose file.  For standalone deployments, set it in a `.env` file or pass it directly to `docker run`:

```bash
docker run -p 8501:8501 -e API_BASE_URL=http://<api-host>:8080 dm2-dashboard:latest
```

---

## CI/CD — Automated Docker Build

The repository includes a GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that automatically builds and pushes the Docker image to Docker Hub on every push to `main`.

**Image:** `mosalehian/digital-formulator-dashboard:latest`

To enable this in your fork, add the following repository secrets under  
**Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub access token (hub.docker.com → Account Settings → Security) |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `requests` | HTTP client for API calls |
| `pandas` | Tabular data handling |
| `plotly` | Interactive charts (PSD, AR, compressibility, pie) |
| `python-dotenv` | `.env` file loading |

---

## Related Repositories

| Repository | Description |
|-----------|-------------|
| [strath-cmac/digital-formulator](https://github.com/strath-cmac/digital-formulator) | FastAPI backend — system of ML models |

---

## Authors

Mohammad Salehian — University of Strathclyde / CMAC
