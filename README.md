# 🎯 AdaptIQ — Intelligent Adaptive Computerized Testing (CAT) Platform

> An enterprise-grade, psychometrically rigorous Computerized Adaptive Testing (CAT) and AI-driven assessment engine built with **Django 5**, **Item Response Theory (2PL IRT)**, **XGBoost machine learning**, **Groq LLaMA-3.3 LLM question synthesis**, and **real-time browser-native WebRTC webcam proctoring**.

---

## 🌟 Key Features & Architecture

### 🧠 1. Psychometric & Machine Learning Engine
- **Item Response Theory (2PL IRT Model)**: Dynamic ability estimation ($\theta$) updated after every item response using Bayesian Maximum Likelihood Estimation (MLE) and Fisher Information maximization.
- **XGBoost Ability Trajectory Predictor**: Machine-learning-assisted convergence acceleration that predicts final latent trait scores from early-stage response sequences.
- **Adaptive Question Selection**: Dynamically selects questions matching the test-taker's evolving difficulty threshold, minimizing standard error of measurement ($SE$).

### 🤖 2. Generative AI Question Engine (Groq LLaMA 3.3)
- Automated extraction from academic PDFs via `PyMuPDF`.
- High-yield MCQ generation with Bloom's taxonomy tagging (Remembering, Understanding, Applying, Analyzing, Evaluating).
- Multi-dimensional distractor rationale and justification generation for comprehensive student feedback.

### 🛡️ 3. Full-Spectrum Anti-Cheat & WebRTC Proctoring
- **Hardware-Level Webcam Monitoring**: Browser-native WebRTC floating proctor video widget with picture-in-picture draggable/minimizable controls, active lens indicators, and clean hardware release upon test completion.
- **Full-Screen Enforcement**: Automatic lock-in with countdown warnings for exit attempts.
- **Telemetry & Tab-Switch Tracking**: Real-time violation logging with automated termination thresholds.
- **Disablements**: Context menu, copy/paste, DevTools hotkeys, and multi-monitor defense.

### 📊 4. Student Analytics & Deep Diagnostic Hub
- **Tabbed Student Dashboard**: Instant access to ongoing tests and complete historical attempts with scores, completion times, and latent ability ($\theta$).
- **5-Section Question Breakdown Drawer**:
  - Detailed Step-by-Step Rationale
  - Core Theoretical Foundation
  - Distractor & Common Misconception Analysis
  - Strategic Exam Takeaways
  - Real-Time Psychometric Telemetry (Difficulty $b$, Discrimination $a$, Fisher Information)
- **Zero-Dependency Native HTML5 Visualizations**:
  - Interactive $\theta$ Trajectory with $\pm 1 \text{ SE}$ Confidence Band
  - Fisher Item Information Distribution Charts

---

## 🏗️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.12+, Django 5.2, Django REST Framework |
| **Psychometrics & ML** | SciPy, NumPy, Scikit-learn, XGBoost, Joblib |
| **Generative AI** | Groq API (`llama-3.3-70b-versatile`), PyMuPDF |
| **Frontend & UI** | Semantic HTML5, Native WebRTC MediaStream API, Vanilla CSS (Glassmorphism, Dark/Light palettes, responsive layouts) |
| **Database** | SQLite (Default Dev) / PostgreSQL (Production-ready) |
| **Testing** | Django Automated Test Suite (63 passing unit/integration tests) |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Clone Repository
```bash
git clone https://github.com/swarna123873/OnlineQuizeApp.git
cd OnlineQuizeApp
```

### 3. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update your `.env` with your Groq API key:
```ini
SECRET_KEY=your-secure-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 6. Run Migrations & Seed Default Academic Data
```bash
python manage.py migrate
```

### 7. Run Test Suite
```bash
python manage.py test tests
```
*All 63 automated unit & integration tests will verify the psychometric engine, anti-cheat mechanisms, and student review pipelines.*

### 8. Start Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 📂 Project Structure

```
├── academics/        # Departments, courses, subjects & academic hierarchy
├── accounts/         # Custom user model (Student, Faculty, Admin), auth & profiles
├── analytics/        # System-wide reporting and psychometric audit logs
├── assessments/      # CAT exam lifecycle, anti-cheat listeners, timer & results
├── config/           # Django settings, root URLs, WSGI/ASGI configuration
├── content/          # PDF ingestion, Groq LLM service & question bank management
├── ml/               # XGBoost latent trait models, training & inference pipelines
├── psychometrics/    # 2PL IRT calculation, Fisher information, MLE/EAP estimators
├── static/           # Modular CSS styling, authentication scripts, proctor widgets
├── templates/        # Responsive HTML templates with glassmorphic design system
└── tests/            # End-to-end unit, integration & psychometric verification tests
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
