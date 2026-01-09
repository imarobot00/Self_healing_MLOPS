# 👀 What You Can See Right Now in Your Monitoring Stack

You mentioned you "saw nothing" - that's actually expected! Let me explain what's available NOW vs what comes in Week 4.

---

## 🎯 Why ML Dashboards Are Empty

The **ML-specific dashboards** (predictions, model performance, training) are empty because:
- ❌ API service (port 8000) is not running
- ❌ Training service (port 8001) is not running  
- ❌ Orchestrator service (port 8002) is not running

These will be **containerized and started in Week 4**. Right now, you're seeing infrastructure monitoring only.

---

## ✅ What IS Available Right Now

### 1. System Metrics (Your Computer's Resources)

**Go to Prometheus**: http://localhost:9090

Click **Graph** tab, paste these queries, click **Execute**:

#### Your CPU Usage:
```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

#### Your Memory Usage (%):
```promql
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

#### Available Memory (GB):
```promql
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024
```

#### Disk Space Available:
```promql
node_filesystem_avail_bytes{fstype!="tmpfs"} / 1024 / 1024 / 1024
```

#### Network Traffic (bytes/sec):
```promql
rate(node_network_receive_bytes_total[5m])
```

### 2. Container Metrics (Monitoring Stack Containers)

#### Memory per Container (MB):
```promql
sum(container_memory_usage_bytes{name!=""}) by (name) / 1024 / 1024
```

You should see:
- `mlops-prometheus` - ~40-60 MB
- `mlops-grafana` - ~100-150 MB
- `mlops-alertmanager` - ~20-30 MB
- `mlops-cadvisor` - ~40-50 MB
- `mlops-node-exporter` - ~10-20 MB

#### CPU per Container:
```promql
sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) by (name)
```

### 3. Prometheus Itself

#### Number of Metrics Being Collected:
```promql
prometheus_tsdb_head_samples
```
You should see **thousands** of metrics being stored!

#### Scrape Status (How Many Targets Are Working):
```promql
up
```
You should see `1` for each working service (prometheus, grafana, node-exporter, cadvisor)

---

## 🎨 How to Use Grafana (Even Though ML Dashboards Are Empty)

**Go to Grafana**: http://localhost:3000
- **Login**: admin / admin

### Create a Simple Dashboard to See System Metrics:

1. Click **+** (top right) → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** datasource
4. In the query field, paste:
   ```promql
   100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
   ```
5. Panel title: "CPU Usage %"
6. Click **Apply**

You now have a live graph of your CPU!

### Add Memory Panel:

1. Click **Add** → **Visualization**
2. Query:
   ```promql
   100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
   ```
3. Title: "Memory Usage %"
4. Click **Apply**

---

## 🔍 Explore What's Being Monitored

### View All Available Metrics

1. Go to **Prometheus**: http://localhost:9090
2. Click **Graph**
3. Click the **Metrics Explorer** button (looks like a grid icon)
4. Search for:
   - `node_` - System metrics (CPU, memory, disk, network)
   - `container_` - Container metrics
   - `prometheus_` - Prometheus internal metrics
   - `grafana_` - Grafana metrics

You'll see **hundreds of metrics**!

### Example: See All Node Metrics

Type `node_` in the query box and you'll see options like:
- `node_cpu_seconds_total` - CPU time
- `node_memory_MemTotal_bytes` - Total RAM
- `node_disk_io_time_seconds_total` - Disk activity
- `node_network_receive_bytes_total` - Network received
- And many more!

---

## 🎯 Check Prometheus Targets

**Go to**: http://localhost:9090/targets

You should see:

### ✅ UP (4 targets):
- **prometheus** - Monitoring itself
- **node-exporter** - Your system metrics
- **cadvisor** - Container metrics
- **grafana** - Visualization service

### ❌ DOWN (3 targets - This is EXPECTED):
- **mlops-api** - Connection refused (not running yet)
- **mlops-training** - Connection refused (not running yet)
- **mlops-orchestrator** - Connection refused (not running yet)

This is **completely normal**! These services don't exist yet.

---

## 🔔 Check Alert Rules

**Go to**: http://localhost:9090/alerts

You'll see **25+ alert rules** configured:
- Most are **Inactive** (green) - this is good!
- Some might be **Pending** or **Firing** (red) for the DOWN services - this is expected

Example alerts you might see firing:
- `APIDown` - Because API isn't running
- `NoPredictions` - Because API isn't making predictions

**This is normal!** Alerts will stop firing once services are running in Week 4.

---

## 📊 View Alert Manager

**Go to**: http://localhost:9093

You should see the Alert Manager UI with:
- Any active alerts
- Silence options
- Routing tree

---

## 🐳 View cAdvisor (Container Monitor)

**Go to**: http://localhost:8080

You'll see a UI showing:
- All running containers
- CPU usage per container
- Memory usage per container
- Network traffic
- Real-time graphs

Click on any container name to see detailed metrics!

---

## ✅ What You SHOULD See

### In Prometheus (http://localhost:9090):
1. **Graph tab**: Paste queries and see real-time graphs
2. **Targets**: 4 UP, 3 DOWN
3. **Alerts**: Rules loaded (some firing for DOWN services)
4. **Status → Targets**: See scrape health

### In Grafana (http://localhost:3000):
1. **MLOps folder**: 2 dashboards (mostly empty because ML services aren't running)
2. **Datasources**: Prometheus configured automatically
3. **Create your own**: Add panels with system metrics

### In Alert Manager (http://localhost:9093):
1. Alerts from Prometheus
2. Routing rules
3. Silences

### In cAdvisor (http://localhost:8080):
1. Container list
2. Resource usage graphs
3. Real-time monitoring

---

## 🎬 Quick Demo: Prove It's Working

### 1. Check Your Live CPU Usage

Open: http://localhost:9090/graph

Paste:
```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Click **Execute**

You should see a graph showing your CPU usage over the last hour!

### 2. See Your Memory

Paste:
```promql
node_memory_MemTotal_bytes / 1024 / 1024 / 1024
```

This shows your total RAM in GB.

### 3. Watch Container Memory

Paste:
```promql
sum(container_memory_usage_bytes{name=~"mlops.*"}) by (name) / 1024 / 1024
```

This shows memory usage of your monitoring containers in MB.

---

## ❓ Why Can't I See ML Metrics?

Because the ML services aren't containerized yet! Here's what's missing:

### What You CAN'T See Yet:
- ❌ Prediction requests/sec
- ❌ Prediction latency
- ❌ Model performance (MAE, R²)
- ❌ Model drift (PSI)
- ❌ Training runs
- ❌ Validation results
- ❌ Model registry stats

### When Will I See Them?
**Week 4** - Once we containerize the API, training service, and orchestrator, all these metrics will start flowing in and the dashboards will come alive!

---

## 🎯 What to Explore Right Now

### 1. Play with Prometheus Queries
Try these and modify them:
```promql
# How much RAM do you have?
node_memory_MemTotal_bytes / 1024 / 1024 / 1024

# CPU cores
count(node_cpu_seconds_total{mode="idle"})

# Disk space left
node_filesystem_free_bytes{fstype!="tmpfs"} / 1024 / 1024 / 1024

# Network speed
rate(node_network_receive_bytes_total[1m])
```

### 2. Create Custom Grafana Dashboards
Build a dashboard showing:
- Your CPU usage
- Your memory usage  
- Your disk space
- Network traffic

### 3. Explore cAdvisor
Go to http://localhost:8080 and:
- Click on container names
- View detailed resource graphs
- See historical data

### 4. Check Alert Rules
Go to http://localhost:9090/alerts and:
- See what conditions trigger each alert
- Note which are firing (for DOWN services)
- Read the descriptions and runbooks

---

## 📅 What Happens in Week 4

Once we containerize the ML services:

1. **API Container** starts on port 8000
   - Prometheus starts scraping `/metrics/prometheus`
   - Predictions metrics start flowing
   - Model performance tracked
   
2. **Training Container** starts on port 8001
   - Training runs tracked
   - Model validation results
   - Registry updates

3. **Orchestrator Container** starts on port 8002
   - Self-healing workflows
   - Drift detection
   - Auto-retraining triggers

4. **Grafana Dashboards Come Alive**
   - ML System Overview shows real data
   - Training Pipeline dashboard populates
   - Alerts start firing on real issues

---

## 🎉 Summary

**What's Working NOW:**
- ✅ Prometheus collecting 1000+ system metrics
- ✅ Grafana ready for visualization
- ✅ Alert Manager routing configured
- ✅ System monitoring (CPU, memory, disk, network)
- ✅ Container monitoring (5 containers tracked)

**What's Coming in Week 4:**
- 🚀 ML service metrics
- 🚀 Model performance tracking
- 🚀 Training pipeline observability
- 🚀 Self-healing workflow monitoring
- 🚀 Live dashboards with real ML data

**Bottom Line:**
The infrastructure is **100% working**! It's collecting system and container metrics right now. The ML-specific parts will light up once we containerize the services in Week 4.

---

## 🔗 Quick Links

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Prometheus Targets**: http://localhost:9090/targets
- **Prometheus Alerts**: http://localhost:9090/alerts
- **Alert Manager**: http://localhost:9093
- **cAdvisor**: http://localhost:8080
- **Node Exporter**: http://localhost:9100/metrics

---

**Try it now!** Open Prometheus, paste a query, and watch your system metrics in real-time! 📊
