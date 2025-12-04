# Autonomous Self-Healing Air Quality Prediction System

This project implements an **AI-powered self-healing monitoring system** that predicts air quality using environmental sensor data (PM2.5, PM1, PM0.3, Temperature, Humidity), detects data drift, identifies anomalies, and automatically retrains or corrects the system when issues arise.

The system is deployed using **FastAPI**, containerized with **Docker**, and hosted on **Azure Virtual Machines**, with full **CI/CD automation** and **monitoring dashboards**.

---

## Objectives

### **1. Build a predictive model for real-time air quality**

Using one year of historical environmental data to train a baseline model that predicts PM2.5 or detects anomalies.

### **2. Implement autonomous self-healing logic**

* Detect **data drift** (KS-test, PSI)
* Detect **concept drift** (error jumps)
* Detect **sensor anomalies** (stuck values, humidity spikes)
* Automatically **retrain** or **fallback** when thresholds are crossed

### **3. Deploy a scalable API service**

* FastAPI service for predictions
* Dockerized for portability
* Hosted on Azure VM with CI/CD

### **4. Add monitoring + alerting system**

* Dashboards (Grafana / Prometheus / custom)
* Real-time anomaly flags
* Automated alerts on failures or drift events

### **5. Ensure reproducible, maintainable MLOps workflow**

* Versioned model artifacts
* Automated pipeline
* Well-structured repository for industry standards

---

##  Components

### **1. Data Layer**

* One-year air quality dataset
* Preprocessing scripts
* Data validation and drift detection

### **2. Model Training Pipeline**

* Feature engineering
* Baseline regression or LSTM model
* Drift monitoring (hourly)
* Automated retraining logic

### **3. FastAPI Inference Service**

* Serves predictions in real time
* Health checks
* Model loading + fallback handling

### **4. Docker Containerization**

* Dockerfile for reproducible deployment
* Images pushed to Azure Container Registry (optional)

### **5. Deployment on Azure Virtual Machines**

* Docker runtime
* Systemd service / Docker Compose
* Private networking + firewall rules

### **6. CI/CD Pipeline**

* GitHub Actions workflows
* Auto-build & auto-deploy on push
* Optionally run tests, linting, and model validation

### **7. Monitoring & Alerting**

* Dashboards for metrics
* Logs & performance monitoring
* Alert thresholds for anomalies and drift

---

##  System Architecture Diagram

![System architecture diagram of the Autonomous Self‑Healing Air Quality Prediction System](Image/archietecture.png)

Figure: High‑level architecture showing data sources, preprocessing, model training & retraining, drift detection & monitoring, FastAPI inference, containerization (Docker), and CI/CD deployment on Azure VMs.



##  Repository Structure

```
self-healing-air-quality/
│
├── data/                 # Raw + processed datasets
├── models/               # Saved model artifacts
├── src/
│   ├── training/         # Training & retraining scripts
│   ├── inference/        # FastAPI app
│   ├── monitoring/       # Drift detection, alerts
│   └── utils/            # Shared utilities
│
├── docker/
│   ├── Dockerfile
│   └── deployment.sh
│
├── ci-cd/
│   └── github-actions.yaml
│
├── docs/
│   └── architecture.png  # Architecture diagram (to be added)
│
└── README.md
```

---

##  Features Roadmap

* [x] Architecture design
* [ ] Baseline prediction model
* [ ] Drift detection module
* [ ] Self-healing retraining logic
* [ ] FastAPI service
* [ ] Docker containerization
* [ ] Azure VM deployment
* [ ] Monitoring dashboards
* [ ] Alerts system


##  Author

Bipul Dahal — Final-year engineering student building full-stack AI/MLOps systems.

---
