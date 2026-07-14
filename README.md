# Airbnb Data Engineering & Analytics Pipeline

An end-to-end data engineering and analytics pipeline for the **Inside Airbnb** dataset. This project automates data ingestion, profiling, data quality assessment, cleaning, enrichment, dimensional modelling, exploratory data analysis (EDA), statistical analysis, and machine learning for Airbnb price prediction.

The pipeline was developed using **Python**, **Polars**, **Pandas**, **DuckDB**, and **Scikit-learn**, and was evaluated using Airbnb datasets from **Mallorca (Spain)** and **Melbourne (Australia)**.

---

# Features

- Automated data ingestion
- Data profiling and quality assessment
- Data cleaning and preprocessing
- Feature engineering
- Star-schema data warehouse
- Exploratory Data Analysis (EDA)
- Statistical hypothesis testing
- Machine learning price prediction
- Reproducible analytical workflow

---

# Project Structure

```text
airbnb_pipeline/
│
├── Melborne.Australia(This cover Question No.2)
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── warehouse/
│
├── pipeline/(Coverts Question 3)
│   ├── ingest.py
│   ├── profile.py
│   ├── quality.py
│   ├── clean.py
│   ├── enrich.py
│   └── model.py
│
├── notebooks/(Covers Question 4, 5, 6)
│   ├── EDA.ipynb
│   ├── Statistical_Analysis.ipynb
│   └── Data_Science.ipynb
│
├── reports/
│
├── run.py
├── requirements.txt
└── README.md
```

---

# Requirements

- Python 3.12+
- DuckDB
- pip

---

# Installation

Clone the repository.

```bash
git clone <repository-url>
cd airbnb_pipeline
```

Create a virtual environment.

Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

---

# Dependencies

Major libraries used include:

```text
pandas
polars
numpy
duckdb
scipy
statsmodels
scikit-learn
xgboost
matplotlib
seaborn
folium
jupyter
```

---

# Download the Dataset

Download the following files for each city from the Inside Airbnb website.

```
listings.csv.gz
calendar.csv.gz
reviews.csv.gz
neighbourhoods.csv
```

Organize the data as follows:

```text
data/
└── raw/
    ├── mallorca/
    │   ├── listings.csv.gz
    │   ├── calendar.csv.gz
    │   ├── reviews.csv.gz
    │   └── neighbourhoods.csv
    │
    └── melbourne/
        ├── listings.csv.gz
        ├── calendar.csv.gz
        ├── reviews.csv.gz
        └── neighbourhoods.csv
```

---

# Running the Pipeline

Execute the complete ETL pipeline.

```bash
python run.py
```

The pipeline performs:

1. Data ingestion
2. Data profiling
3. Data quality assessment
4. Data cleaning
5. Data enrichment
6. Dimensional modelling
7. Warehouse creation

---

# Data Warehouse

The processed data is stored in DuckDB using a star schema.

## Dimension Tables

- dim_city
- dim_date
- dim_host
- dim_property
- dim_room_type
- dim_neighbourhood

## Fact Tables

- fact_listing
- fact_calendar
- fact_review

---

# Running the Analysis

## Exploratory Data Analysis

```bash
jupyter notebook
```

Open

```
EDA.ipynb
```

The notebook includes:

- Summary statistics
- Price distributions
- Geographic analysis
- Host analysis
- Seasonal trends
- Demand analysis
- Market comparisons

---

## Statistical Analysis

Run

```
Statistical_Analysis.ipynb
```

This notebook includes:

- Hypothesis testing
- Effect size calculations
- Business interpretations

---

## Machine Learning

Run

```
Data_Science.ipynb
```

The notebook performs:

- Feature engineering
- Cross-validation
- Model training
- Model comparison
- Price prediction

Models evaluated:

- Linear Regression
- Random Forest
- XGBoost

Evaluation metrics:

- MAE
- RMSE
- MAPE

---

# Execution Order

Run the project in the following order.

```text
1. Download datasets

↓

2. python run.py

↓

3. EDA.ipynb

↓

4. Statistical_Analysis.ipynb

↓

5. Data_Science.ipynb
```

---

# Outputs

The pipeline generates:

```text
data/
├── interim/
│   └── master_all_cities.parquet
│
├── 
│
└── 
    └── airbnb.duckdb
```

The notebooks produce:

- Summary tables
- Visualizations
- Statistical test results
- Machine learning evaluation tables
- Feature importance plots

---

# Methodology

The project follows a modular ETL workflow.

```text
Raw Airbnb Data
        │
        ▼
Data Ingestion
        │
        ▼
Data Profiling
        │
        ▼
Data Quality Assessment
        │
        ▼
Data Cleaning
        │
        ▼
Feature Engineering
        │
        ▼
Dimensional Modelling
        │
        ▼
DuckDB Warehouse
        │
        ▼
EDA
        │
        ▼
Statistical Analysis
        │
        ▼
Machine Learning
```

---

# Machine Learning Results

Three regression models were evaluated using 5-fold cross-validation.

| Model | MAE | RMSE | MAPE |
|------|------:|------:|------:|
| Linear Regression | 0.4153 | 0.5498 | 0.0696 |
| Random Forest | 0.3722 | 0.5016 | 0.0621 |
| XGBoost | **0.3683** | **0.4894** | **0.0617** |

XGBoost achieved the best overall predictive performance.

---

# Limitations

- Snapshot data rather than continuous historical data
- Missing values requiring imputation
- No external factors (weather, events, tourism)
- Explainable AI techniques (SHAP/LIME) not implemented
- Partial residual analysis

---

# Future Work

Potential future improvements include:

- Incremental ETL
- Hyperparameter optimization
- SHAP/LIME explainability
- Interactive dashboards
- Cloud deployment
- Automated data quality monitoring
- Additional external data sources

---

# AI Usage

The following AI tools were used during development.

| Tool | Purpose |
|------|----------|
| Google Gemini | Business interpretation and market analysis |
| Claude | Code generation, debugging, and refactoring |
| ChatGPT (GPT-5.5) | Test generation, documentation, statistical explanations, and report writing |

All generated code and analytical interpretations were manually reviewed, executed, and validated before inclusion in the project.

---

# License

This project was developed for academic purposes.
