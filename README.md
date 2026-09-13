# 💊 MediTrace — Pharmacy Inventory & Expiry Tracking System

**MediTrace** is a pharmacy inventory management system built with Django and Chart.js. It provides real-time stock velocity tracking, proactive expiry detection, and automated consumption-based reorder recommendations with a clean dual-theme (Light/Dark) UI.

---

## 🚀 Key Features

- **Core Pharmacy Inventory**: Manage Medicines, Batches, Stock Inflow/Outflow (`StockTransaction`), and Suppliers with comprehensive search and filtering in Django Admin.
- **Consumption-Based Reorder Engine**:
  - Dynamically calculates average daily consumption over configurable windows (7, 14, 30, 60, 90 days).
  - Automatically flags medicines as **REORDER NOW** ($<7$ days), **REORDER SOON** ($<14$ days), or **OK**.
  - Handles zero consumption edge cases gracefully (`INSUFFICIENT DATA`).
- **Proactive Expiry Alert System**:
  - `python manage.py check_expiry` CLI tool to flag expired and near-expiry batches across configurable thresholds.
- **Expiry Wastage Analytics**:
  - Tracks unused stock in expired batches, calculating total unit wastage and financial loss ($) by medicine and month.
- **Interactive Chart.js Dashboard**:
  - Dual-axis line chart for net inventory balance and daily inflow/outflow movements.
  - Bar chart for expiry wastage analysis.
  - Interactive reorder status table with color-coded badges.
  - **Light Mode (Default)** & **Dark Mode** toggle with `localStorage` persistence.

---

## 🛠️ Tech Stack

- **Backend**: Django (Python 3.13)
- **Database**: SQLite (Default)
- **Frontend / Visualizations**: Vanilla CSS, Chart.js via CDN, Google Fonts (Inter)
- **CLI & Management**: Django Management Commands (`check_expiry`, `seed_data`)

---

## 📂 Project Structure

```
MediTrace/
├── manage.py
├── meditrace/              # Project configuration (settings, URLs)
├── inventory/              # Core pharmacy inventory (Medicine, Batch, StockTransaction)
├── suppliers/              # Supplier management
├── alerts/                 # Expiry checker management command
├── dashboard/              # Analytics services, APIs, and Chart.js views
├── templates/              # Dashboard HTML templates
├── static/                 # Static assets
├── requirements.txt
└── README.md
```

---

## ⚡ Quickstart Guide

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/shreyash-hh/MediTrace.git
cd MediTrace

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Apply Migrations & Seed Sample Data

```bash
python manage.py migrate
python manage.py seed_data
```

### 3. Create Superuser (Admin Access)

```bash
python manage.py createsuperuser
```
*(Default seeded superuser: `admin` / `admin123`)*

### 4. Run the Application

```bash
python manage.py runserver
```

- **Analytics Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Django Admin Portal**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Stock Summary Telemetry API**: [http://127.0.0.1:8000/dashboard/api/stock-summary/](http://127.0.0.1:8000/dashboard/api/stock-summary/)

---

## 🧪 CLI Commands & Testing

### Check Expiry Alerts
```bash
# Default 30 days
python manage.py check_expiry

# Custom threshold
python manage.py check_expiry --days 60
```

### Run Test Suite
```bash
python manage.py test
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
