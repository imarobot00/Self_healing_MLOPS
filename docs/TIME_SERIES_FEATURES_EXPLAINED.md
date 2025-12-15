# Time Series Feature Engineering for Air Quality Prediction
## A Comprehensive Theoretical Guide

---

## Table of Contents
1. [Introduction to Time Series Features](#introduction)
2. [Lag Features](#lag-features)
3. [Rolling Window Statistics](#rolling-window-statistics)
4. [Change Rates and Derivatives](#change-rates)
5. [Why These Features Matter](#why-these-features-matter)
6. [Feature Comparison: AQI vs PM2.5 Models](#feature-comparison)
7. [Mathematical Foundations](#mathematical-foundations)
8. [Practical Implementation](#practical-implementation)
9. [Feature Engineering Best Practices](#best-practices)

---

## 1. Introduction to Time Series Features {#introduction}

### What is Time Series Data?

Time series data is a sequence of observations recorded at different time intervals. In our case:
- **Observations**: AQI, PM2.5, temperature, humidity measurements
- **Time Intervals**: Hourly measurements (every 1 hour)
- **Sequence**: Data points ordered chronologically

### The Core Problem

**Question**: How do we predict what will happen *next*?

**Challenge**: Future values often depend on past patterns, trends, and changes. A single snapshot isn't enough.

**Solution**: Extract meaningful information from historical data using **feature engineering**.

### Three Fundamental Categories of Time Series Features

```
┌─────────────────────────────────────────────────────────────┐
│                    TIME SERIES FEATURES                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. LAG FEATURES          2. ROLLING STATISTICS            │
│     "What happened          "What's the pattern            │
│      in the past?"          over a time window?"           │
│                                                             │
│     ┌──┬──┬──┬──┐          ┌────────────────┐            │
│     │-3│-2│-1│ ? │          │  Window Size   │            │
│     └──┴──┴──┴──┘          │  ┌──┬──┬──┐   │            │
│      Past  Now              │  │  │  │  │   │            │
│                             │  └──┴──┴──┘   │            │
│                             └────────────────┘            │
│                                                             │
│  3. CHANGE RATES                                           │
│     "How fast is it changing?"                             │
│                                                             │
│     ┌──────────────────┐                                  │
│     │   Δ / Δt         │                                  │
│     │  (derivative)    │                                  │
│     └──────────────────┘                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Lag Features {#lag-features}

### 2.1 Theoretical Foundation

**Definition**: A lag feature is the value of a variable at a previous time step.

**Notation**: 
- `X(t)` = Current value at time `t`
- `X(t-1)` = Value 1 time step ago (lag 1)
- `X(t-k)` = Value k time steps ago (lag k)

### 2.2 Why Lag Features Work

**Autocorrelation**: Many time series exhibit autocorrelation - correlation with their own past values.

```
Example: Air Quality Index (AQI)

Time:     t-3    t-2    t-1     t      t+1
Value:    120    125    130    ???     ???
          ↑      ↑      ↑
          │      │      └─── If AQI was 130 an hour ago,
          │      │            it's likely still high now
          │      └────────── Trend information
          └───────────────── Pattern recognition
```

### 2.3 Different Lag Intervals

#### Short-Term Lags (1-3 hours)
**Purpose**: Capture immediate recent conditions
- `aqi_lag_1`: AQI 1 hour ago
- `aqi_lag_2`: AQI 2 hours ago
- `aqi_lag_3`: AQI 3 hours ago

**Use Case**: If pollution was high 1 hour ago, it's probably still high now.

```
Real Example from Kathmandu:
07:00 AM → AQI = 200 (Very Unhealthy)
08:00 AM → AQI = ??? 
           Prediction uses: aqi_lag_1 = 200
           Likely result: Still high (190-210 range)
```

#### Medium-Term Lags (6-12 hours)
**Purpose**: Capture daily patterns and transitions
- `aqi_lag_6`: AQI 6 hours ago
- `aqi_lag_12`: AQI 12 hours ago

**Use Case**: Detect shifts from night to morning or morning to afternoon.

```
Example: Morning Traffic Pattern
01:00 AM (night)    → AQI = 150 (low traffic)
07:00 AM (morning)  → AQI = ??? 
                     Uses: aqi_lag_6 = 150 (was nighttime)
                     Model learns: Morning rush hour increases AQI
```

#### Long-Term Lags (24 hours)
**Purpose**: Capture daily seasonality
- `aqi_lag_24`: AQI exactly 24 hours ago (same time yesterday)

**Use Case**: "What was it like at this exact time yesterday?"

```
Example: Same-Time-Yesterday Pattern
Monday 7:00 AM    → AQI = 190 (rush hour)
Tuesday 7:00 AM   → AQI = ???
                   Uses: aqi_lag_24 = 190
                   Model learns: Same time = similar conditions
```

### 2.4 Why PM2.5 Has Fewer Lags

**AQI Lags**: 1, 2, 3, 6, 12, 24 hours = **6 lag features**  
**PM2.5 Lags**: 1, 3, 6 hours = **3 lag features**

**Reason**: In our preprocessing pipeline:
- **AQI is the TARGET variable** → Gets full feature engineering treatment
- **PM2.5 is an INPUT variable** → Gets minimal lag features to avoid overfitting

```python
# Preprocessing Logic (Simplified)
if variable == target_variable:  # AQI
    create_lags = [1, 2, 3, 6, 12, 24]  # Comprehensive
else:  # PM2.5, temperature, etc.
    create_lags = [1, 3, 6]  # Basic
```

---

## 3. Rolling Window Statistics {#rolling-window-statistics}

### 3.1 Theoretical Foundation

**Definition**: Statistical summaries computed over a sliding window of past observations.

**Window**: A fixed-size subset of sequential data points.

```
Timeline with Window Size = 3:
┌───┬───┬───┬───┬───┬───┬───┐
│100│110│120│130│140│150│ ? │
└───┴───┴───┴───┴───┴───┴───┘
        └───┴───┴───┘
         Window at t-3

Calculate: mean, std, min, max of this window
```

### 3.2 Four Core Rolling Statistics

#### A. Rolling Mean (Average)

**Formula**: 
```
rolling_mean(window_size) = (1/n) × Σ X(t-i) for i = 0 to n-1
```

**Interpretation**: The average value over the window period.

**Use Case**: Smooths out short-term fluctuations, reveals underlying trends.

```
Example: 3-Hour Rolling Mean
Time:     10:00   11:00   12:00   13:00
AQI:      100     120     140     ???
                  └───┴───┴───┘
          rolling_mean_3 = (100+120+140)/3 = 120

Meaning: On average, AQI was 120 over the past 3 hours
```

#### B. Rolling Standard Deviation (Volatility)

**Formula**:
```
rolling_std(window_size) = sqrt[(1/n) × Σ (X(t-i) - mean)²]
```

**Interpretation**: How much variability exists in the window.

**Use Case**: Detect periods of stable vs unstable air quality.

```
Example: Stable vs Unstable Periods

Stable Period:
Time:     10:00   11:00   12:00
AQI:      150     152     148
rolling_std_3 = 2.0 (low variance → stable)

Unstable Period:
Time:     10:00   11:00   12:00
AQI:      100     180     120
rolling_std_3 = 41.6 (high variance → chaotic)

Interpretation: High std → unpredictable, may spike or drop
                Low std  → steady conditions, easier to predict
```

#### C. Rolling Minimum (Floor)

**Formula**:
```
rolling_min(window_size) = min(X(t-i)) for i = 0 to n-1
```

**Interpretation**: Best air quality in the window.

**Use Case**: Identify if conditions improved recently.

```
Example: Recovery Detection
Time:     10:00   11:00   12:00   13:00
AQI:      180     150     120     ???
rolling_min_3 = 120

Meaning: Air quality improved to 120 at some point
         → Might indicate a positive trend
```

#### D. Rolling Maximum (Ceiling)

**Formula**:
```
rolling_max(window_size) = max(X(t-i)) for i = 0 to n-1
```

**Interpretation**: Worst air quality in the window.

**Use Case**: Detect recent pollution spikes.

```
Example: Spike Detection
Time:     10:00   11:00   12:00   13:00
AQI:      120     200     130     ???
rolling_max_3 = 200

Meaning: There was a spike to 200 recently
         → System may still be recovering
```

### 3.3 Window Sizes and Their Meanings

Our models use **4 window sizes**: 3, 6, 12, 24 hours

#### 3-Hour Window (Short-Term)
```
┌─────────────────┐
│  3-Hour Window  │
├─────────────────┤
│ Captures:       │
│ - Recent trends │
│ - Immediate     │
│   fluctuations  │
└─────────────────┘
```
**Example**: Morning rush hour pattern (6 AM - 9 AM)

#### 6-Hour Window (Medium-Short-Term)
```
┌─────────────────┐
│  6-Hour Window  │
├─────────────────┤
│ Captures:       │
│ - Half-day      │
│   patterns      │
│ - Morning or    │
│   afternoon     │
│   periods       │
└─────────────────┘
```
**Example**: Full morning period (6 AM - 12 PM)

#### 12-Hour Window (Medium-Long-Term)
```
┌─────────────────┐
│ 12-Hour Window  │
├─────────────────┤
│ Captures:       │
│ - Day/night     │
│   cycle halves  │
│ - Major daily   │
│   transitions   │
└─────────────────┘
```
**Example**: Daytime vs nighttime patterns

#### 24-Hour Window (Long-Term)
```
┌─────────────────┐
│ 24-Hour Window  │
├─────────────────┤
│ Captures:       │
│ - Full daily    │
│   cycle         │
│ - Weekly        │
│   patterns      │
└─────────────────┘
```
**Example**: Complete daily pollution cycle

### 3.4 Complete Rolling Feature Set

**For each window size**, we compute **4 statistics** = 4 windows × 4 stats = **16 rolling features**

```
AQI Rolling Features (16 total):

Window = 3 hours:
  ├── aqi_rolling_mean_3
  ├── aqi_rolling_std_3
  ├── aqi_rolling_min_3
  └── aqi_rolling_max_3

Window = 6 hours:
  ├── aqi_rolling_mean_6
  ├── aqi_rolling_std_6
  ├── aqi_rolling_min_6
  └── aqi_rolling_max_6

Window = 12 hours:
  ├── aqi_rolling_mean_12
  ├── aqi_rolling_std_12
  ├── aqi_rolling_min_12
  └── aqi_rolling_max_12

Window = 24 hours:
  ├── aqi_rolling_mean_24
  ├── aqi_rolling_std_24
  ├── aqi_rolling_min_24
  └── aqi_rolling_max_24
```

### 3.5 Why PM2.5 Has NO Rolling Features

**AQI**: 16 rolling features (4 windows × 4 statistics)  
**PM2.5**: 0 rolling features

**Reason**: Computational and overfitting concerns
- Rolling statistics are expensive to compute
- Only the **target variable** (AQI) gets full treatment
- Input variables (PM2.5) get basic lags only

```
Design Decision:
┌────────────────────────────────────────┐
│  Target Variable (AQI)                 │
│  → Full feature engineering            │
│  → Lags + Rolling stats + Change rates │
├────────────────────────────────────────┤
│  Input Variables (PM2.5, temp, etc.)   │
│  → Minimal feature engineering         │
│  → Only basic lags                     │
└────────────────────────────────────────┘
```

---

## 4. Change Rates and Derivatives {#change-rates}

### 4.1 Theoretical Foundation

**Definition**: The rate at which a variable changes over time.

**Mathematical Concept**: Discrete derivative

```
Change Rate = Δ Value / Δ Time
            = (Value_now - Value_before) / Time_interval
```

### 4.2 Three Types of Change Features

#### A. 1-Hour Change (Short-Term Momentum)

**Formula**:
```
aqi_change_1h = AQI(t) - AQI(t-1)
```

**Interpretation**: How much AQI changed in the last hour.

```
Example: Detecting Rapid Increases
Time:     10:00   11:00
AQI:      120     160
change_1h = 160 - 120 = +40 (rapid increase!)

Meaning: AQI jumped 40 points in 1 hour
         → Likely pollution event (traffic surge, fire, etc.)
         → Next hour may continue increasing
```

**Use Cases**:
- **Positive change** (+): Worsening conditions
- **Negative change** (-): Improving conditions
- **Near zero** (0): Stable conditions

#### B. 3-Hour Change (Medium-Term Trend)

**Formula**:
```
aqi_change_3h = AQI(t) - AQI(t-3)
```

**Interpretation**: Net change over 3 hours.

```
Example: Morning Rush Hour
Time:     07:00   08:00   09:00   10:00
AQI:      100     140     180     190
change_3h = 190 - 100 = +90 (strong upward trend)

Meaning: AQI increased 90 points over 3 hours
         → Sustained pollution buildup
         → Morning traffic pattern confirmed
```

#### C. Change Rate (Acceleration)

**Formula**:
```
aqi_change_rate = (AQI(t) - AQI(t-1)) / AQI(t-1)
                = Percentage change per hour
```

**Interpretation**: Relative rate of change (normalized).

```
Example: Percentage Change

Scenario 1: Low AQI spike
Time:     10:00   11:00
AQI:      50      60
change_rate = (60-50)/50 = 0.20 = +20% increase

Scenario 2: High AQI spike
Time:     10:00   11:00
AQI:      200     240
change_rate = (240-200)/200 = 0.20 = +20% increase

Meaning: Both scenarios have same RELATIVE change (20%)
         → Useful for comparing changes at different scales
```

### 4.3 Why Change Features Matter

**Problem**: Lags tell you WHERE you were, not WHICH DIRECTION you're going.

```
Example: Same Lag, Different Outcomes

Scenario A: Improving Conditions
Time:     09:00   10:00   11:00   12:00
AQI:      200     180     160     ???
lag_1 = 160, but change_1h = -20 (improving!)

Scenario B: Worsening Conditions
Time:     09:00   10:00   11:00   12:00
AQI:      120     140     160     ???
lag_1 = 160, but change_1h = +20 (worsening!)

Same lag value, opposite trends!
Change features capture the DIRECTION.
```

### 4.4 Complete Change Feature Set

```
AQI Change Features (3 total):

├── aqi_change_1h
│   └── Short-term momentum (hourly)
│
├── aqi_change_3h
│   └── Medium-term trend (3-hourly)
│
└── aqi_change_rate
    └── Relative change rate (percentage)
```

**PM2.5**: 0 change features (same reason as rolling features)

---

## 5. Why These Features Matter {#why-these-features-matter}

### 5.1 The Machine Learning Perspective

**Raw Data Problem**:
```
Input:  AQI_now = 150
Output: AQI_next = ???

Model thinks: "I only know it's 150 right now.
               No idea if it's rising, falling, or stable.
               Can't make a good prediction!"
```

**Enriched Data Solution**:
```
Input:  AQI_now = 150
        lag_1 = 140 (was 140 an hour ago → rising)
        lag_24 = 145 (similar yesterday)
        rolling_mean_3 = 148 (trending up)
        rolling_std_3 = 5 (stable, not chaotic)
        change_1h = +10 (increasing)
        change_rate = +7% (accelerating)
        
Output: AQI_next = 158 (confident prediction)

Model thinks: "It's been steadily rising for 3 hours,
               similar pattern to yesterday,
               upward momentum continuing.
               Predict: 158 (8 point increase)"
```

### 5.2 Information Hierarchy

```
┌──────────────────────────────────────────────────┐
│            INFORMATION RICHNESS PYRAMID          │
├──────────────────────────────────────────────────┤
│                                                  │
│                   △ MOST INFO                    │
│                  △ △                             │
│                 △ △ △                            │
│                △ △ △ △                           │
│               △ △ △ △ △                          │
│              ────────────                        │
│              ROLLING STATS                       │
│         (Patterns + Volatility)                  │
│                                                  │
│            ──────────────────                    │
│            CHANGE FEATURES                       │
│          (Direction + Speed)                     │
│                                                  │
│          ────────────────────────                │
│               LAG FEATURES                       │
│           (Historical Values)                    │
│                                                  │
│        ──────────────────────────────            │
│              CURRENT VALUE                       │
│             (Single Point)                       │
│                                                  │
│                 △ LEAST INFO                     │
└──────────────────────────────────────────────────┘
```

### 5.3 Real-World Example: Predicting Morning Rush Hour

**Scenario**: It's 8:00 AM in Kathmandu. Predict AQI at 9:00 AM.

**What the Model Sees**:

```
Current State (8:00 AM):
├── AQI_now = 180
│
├── LAG FEATURES (Historical Context)
│   ├── lag_1 = 160 (7:00 AM was 160)
│   ├── lag_2 = 140 (6:00 AM was 140)
│   ├── lag_3 = 120 (5:00 AM was 120)
│   └── lag_24 = 175 (8:00 AM yesterday was 175)
│       → Interpretation: Same time yesterday was similar!
│
├── ROLLING FEATURES (Pattern Detection)
│   ├── rolling_mean_3 = 140 (average: 120→140→160→180)
│   │   → Interpretation: Trending upward
│   ├── rolling_std_3 = 24.5
│   │   → Interpretation: Moderate variability
│   ├── rolling_min_3 = 120
│   │   → Interpretation: Started at 120
│   └── rolling_max_3 = 180
│       → Interpretation: Peak is NOW (8:00 AM)
│
└── CHANGE FEATURES (Momentum)
    ├── change_1h = +20 (increased 20 points last hour)
    │   → Interpretation: Strong upward momentum
    ├── change_3h = +60 (increased 60 points over 3 hours)
    │   → Interpretation: Sustained buildup (rush hour!)
    └── change_rate = +12.5%
        → Interpretation: 12.5% increase rate

MODEL REASONING:
"At 8 AM, AQI is 180. It's been rising steadily (+60 over 3 hours).
 Yesterday at this time was 175, peaked at 200 by 9 AM.
 Current momentum is +20/hour.
 Pattern matches: morning rush hour.
 
 PREDICTION: AQI at 9:00 AM = 195
 (continuing upward trend, approaching daily peak)"
```

---

## 6. Feature Comparison: AQI vs PM2.5 Models {#feature-comparison}

### 6.1 Feature Count Summary

```
╔═══════════════════════════════════════════════════════════════╗
║                    FEATURE ENGINEERING COMPARISON              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  ┌─────────────────────────────────────────────────────┐    ║
║  │              AQI MODEL (TARGET VARIABLE)            │    ║
║  ├─────────────────────────────────────────────────────┤    ║
║  │  LAG FEATURES:           6 features                 │    ║
║  │    └── lag_1, lag_2, lag_3, lag_6, lag_12, lag_24  │    ║
║  │                                                      │    ║
║  │  ROLLING STATISTICS:     16 features                │    ║
║  │    ├── 3-hour window:  mean, std, min, max         │    ║
║  │    ├── 6-hour window:  mean, std, min, max         │    ║
║  │    ├── 12-hour window: mean, std, min, max         │    ║
║  │    └── 24-hour window: mean, std, min, max         │    ║
║  │                                                      │    ║
║  │  CHANGE FEATURES:        3 features                 │    ║
║  │    └── change_1h, change_3h, change_rate           │    ║
║  │                                                      │    ║
║  │  TOTAL AQI-SPECIFIC FEATURES: 25                    │    ║
║  └─────────────────────────────────────────────────────┘    ║
║                                                               ║
║  ┌─────────────────────────────────────────────────────┐    ║
║  │            PM2.5 MODEL (INPUT VARIABLE)             │    ║
║  ├─────────────────────────────────────────────────────┤    ║
║  │  LAG FEATURES:           3 features                 │    ║
║  │    └── pm25_lag_1, pm25_lag_3, pm25_lag_6          │    ║
║  │                                                      │    ║
║  │  ROLLING STATISTICS:     0 features                 │    ║
║  │    └── None created                                 │    ║
║  │                                                      │    ║
║  │  CHANGE FEATURES:        0 features                 │    ║
║  │    └── None created                                 │    ║
║  │                                                      │    ║
║  │  TOTAL PM2.5-SPECIFIC FEATURES: 3                   │    ║
║  └─────────────────────────────────────────────────────┘    ║
║                                                               ║
║  RATIO: AQI has 8.3× MORE features than PM2.5                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### 6.2 Why This Difference Exists

#### Design Philosophy

```
┌────────────────────────────────────────────────────────┐
│         FEATURE ENGINEERING STRATEGY                   │
├────────────────────────────────────────────────────────┤
│                                                        │
│  TARGET VARIABLE (What we're predicting)               │
│  ════════════════════════════════════════              │
│  → Gets MAXIMUM feature engineering                    │
│  → All lag intervals                                   │
│  → All rolling statistics                              │
│  → All change rates                                    │
│  → Goal: Extract every possible pattern                │
│                                                        │
│  INPUT VARIABLES (What we use to predict)              │
│  ═══════════════════════════════════════              │
│  → Gets MINIMAL feature engineering                    │
│  → Basic lags only                                     │
│  → No rolling statistics (too expensive)               │
│  → No change rates (prevents overfitting)              │
│  → Goal: Provide context without redundancy            │
│                                                        │
└────────────────────────────────────────────────────────┘
```

#### Technical Reasons

**1. Computational Cost**
```
For AQI (1 variable):
  6 lags + 16 rolling + 3 changes = 25 features

If we did the same for ALL variables (PM2.5, PM1, PM10, temp, humidity, etc.):
  6 variables × 25 features = 150 additional features!
  
Result: Model becomes too complex, slow to train, overfits.
```

**2. Overfitting Prevention**
```
Too many features → Model memorizes training data
                  → Poor generalization
                  → Bad predictions on new data

Solution: Only engineer features for TARGET variable
```

**3. Feature Redundancy**
```
Problem: AQI is calculated FROM PM2.5

If we create full features for both:
  aqi_lag_1 ≈ f(pm25_lag_1)  ← Highly correlated!
  aqi_rolling_mean_3 ≈ f(pm25_rolling_mean_3)
  
Result: Redundant information, no new insights
```

### 6.3 Performance Impact

**This explains the performance difference!**

```
╔══════════════════════════════════════════════════════╗
║             MODEL PERFORMANCE COMPARISON              ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  AQI MODEL                                           ║
║  ├── Features: 25 AQI-specific + other inputs       ║
║  ├── R² Score: 0.932 (93.2% variance explained)     ║
║  ├── MAE: 4.3 AQI points                            ║
║  └── MAPE: 3.2%                                     ║
║      └─> EXCELLENT PERFORMANCE                      ║
║                                                      ║
║  PM2.5 MODEL                                         ║
║  ├── Features: 3 PM2.5-specific + other inputs      ║
║  ├── R² Score: 0.387 (38.7% variance explained)     ║
║  ├── MAE: 46.3 µg/m³                                ║
║  └── MAPE: 16.2%                                    ║
║      └─> ACCEPTABLE PERFORMANCE                     ║
║                                                      ║
╚══════════════════════════════════════════════════════╝

The AQI model has 8× more information about temporal
patterns, trends, and changes → Much better predictions!
```

---

## 7. Mathematical Foundations {#mathematical-foundations}

### 7.1 Formal Definitions

#### Time Series Notation

Let $X(t)$ be the value of a time series at time $t$.

**Discrete Time Series**:
$$X = \{X(t_1), X(t_2), ..., X(t_n)\}$$

where $t_i$ are ordered time points.

#### Lag Operator

**Definition**: The lag operator $L^k$ shifts a time series back by $k$ periods.

$$L^k X(t) = X(t-k)$$

**Properties**:
- $L^0 X(t) = X(t)$ (identity)
- $L^1 X(t) = X(t-1)$ (one period back)
- $L^k \cdot L^m = L^{k+m}$ (composition)

**Example**:
```
If X = [100, 110, 120, 130, 140]

L¹X = [_, 100, 110, 120, 130]  (1 lag)
L²X = [_, _, 100, 110, 120]    (2 lags)
```

#### Rolling Window Statistics

**Rolling Mean** (Moving Average):
$$\text{MA}_n(t) = \frac{1}{n} \sum_{i=0}^{n-1} X(t-i)$$

**Rolling Variance**:
$$\text{Var}_n(t) = \frac{1}{n} \sum_{i=0}^{n-1} \left(X(t-i) - \text{MA}_n(t)\right)^2$$

**Rolling Standard Deviation**:
$$\text{Std}_n(t) = \sqrt{\text{Var}_n(t)}$$

**Rolling Minimum**:
$$\text{Min}_n(t) = \min_{i \in [0, n-1]} X(t-i)$$

**Rolling Maximum**:
$$\text{Max}_n(t) = \max_{i \in [0, n-1]} X(t-i)$$

#### First Difference (Change)

**Absolute Change**:
$$\Delta X(t) = X(t) - X(t-1)$$

**Relative Change** (Rate):
$$\Delta\% X(t) = \frac{X(t) - X(t-1)}{X(t-1)} \times 100\%$$

### 7.2 Information Theory Perspective

#### Entropy and Predictability

**Entropy** measures uncertainty:
$$H(X) = -\sum_{i} p(x_i) \log p(x_i)$$

**Key Insight**: More features → More information → Lower entropy → Better predictions

```
Information Content:

Single Value:       I = log₂(1)      = 0 bits (no info)
+ 1 Lag:           I = log₂(2)      = 1 bit
+ 6 Lags:          I = log₂(6)      = 2.58 bits
+ 16 Rolling Stats: I = log₂(16)     = 4 bits
+ 3 Change Rates:  I = log₂(3)      = 1.58 bits

Total AQI features: ~8 bits of information
Total PM2.5 features: ~2 bits of information

AQI has 4× more information!
```

### 7.3 Signal Processing View

#### Fourier Analysis Analogy

Time series features decompose signals into components:

**Lag Features** ≈ **Time Domain**
- Raw signal at different time points

**Rolling Mean** ≈ **Low-Pass Filter**
- Removes high-frequency noise
- Reveals underlying trend

**Rolling Std** ≈ **High-Pass Filter**
- Captures volatility
- Detects anomalies

**Change Rate** ≈ **Derivative Filter**
- Extracts velocity/acceleration
- Measures momentum

```
Original Signal (AQI):
   ∧   ∧   ∧
  ∧ ∨ ∧ ∨ ∧ ∨  ← Noisy, chaotic
 ∧         ∨

After Rolling Mean:
    ___/‾‾‾\___  ← Smooth, clear trend

Rolling Std shows where volatility spikes occur
Change Rate shows acceleration/deceleration
```

---

## 8. Practical Implementation {#practical-implementation}

### 8.1 Code Example: Creating Lag Features

```python
import pandas as pd

# Sample AQI data
df = pd.DataFrame({
    'datetime': pd.date_range('2025-01-01', periods=100, freq='1H'),
    'aqi': [100, 105, 110, 115, 120, ...]  # AQI values
})

# Create lag features
df['aqi_lag_1'] = df['aqi'].shift(1)   # 1 hour ago
df['aqi_lag_2'] = df['aqi'].shift(2)   # 2 hours ago
df['aqi_lag_3'] = df['aqi'].shift(3)   # 3 hours ago
df['aqi_lag_6'] = df['aqi'].shift(6)   # 6 hours ago
df['aqi_lag_12'] = df['aqi'].shift(12) # 12 hours ago
df['aqi_lag_24'] = df['aqi'].shift(24) # 24 hours ago

print(df.head(30))
```

**Output**:
```
datetime             aqi  lag_1  lag_2  lag_3  lag_6  lag_12  lag_24
2025-01-01 00:00    100   NaN    NaN    NaN    NaN     NaN     NaN
2025-01-01 01:00    105   100    NaN    NaN    NaN     NaN     NaN
2025-01-01 02:00    110   105    100    NaN    NaN     NaN     NaN
2025-01-01 03:00    115   110    105    100    NaN     NaN     NaN
...
2025-01-01 24:00    200   195    190    185    170     150     100
```

### 8.2 Code Example: Creating Rolling Features

```python
# Rolling mean (3-hour window)
df['aqi_rolling_mean_3'] = df['aqi'].rolling(window=3).mean()

# Rolling standard deviation
df['aqi_rolling_std_3'] = df['aqi'].rolling(window=3).std()

# Rolling minimum
df['aqi_rolling_min_3'] = df['aqi'].rolling(window=3).min()

# Rolling maximum
df['aqi_rolling_max_3'] = df['aqi'].rolling(window=3).max()

# Apply for all window sizes
for window in [3, 6, 12, 24]:
    df[f'aqi_rolling_mean_{window}'] = df['aqi'].rolling(window).mean()
    df[f'aqi_rolling_std_{window}'] = df['aqi'].rolling(window).std()
    df[f'aqi_rolling_min_{window}'] = df['aqi'].rolling(window).min()
    df[f'aqi_rolling_max_{window}'] = df['aqi'].rolling(window).max()
```

**Output**:
```
datetime             aqi  mean_3  std_3  min_3  max_3
2025-01-01 00:00    100    NaN     NaN    NaN    NaN
2025-01-01 01:00    105    NaN     NaN    NaN    NaN
2025-01-01 02:00    110   105.0   5.00   100    110
2025-01-01 03:00    115   110.0   5.00   105    115
2025-01-01 04:00    120   115.0   5.00   110    120
```

### 8.3 Code Example: Creating Change Features

```python
# 1-hour change (absolute)
df['aqi_change_1h'] = df['aqi'] - df['aqi'].shift(1)

# 3-hour change (absolute)
df['aqi_change_3h'] = df['aqi'] - df['aqi'].shift(3)

# Change rate (percentage)
df['aqi_change_rate'] = (df['aqi'] - df['aqi'].shift(1)) / df['aqi'].shift(1)

# Or as percentage
df['aqi_change_rate_pct'] = df['aqi_change_rate'] * 100
```

**Output**:
```
datetime             aqi  change_1h  change_3h  change_rate
2025-01-01 00:00    100     NaN         NaN         NaN
2025-01-01 01:00    105     +5          NaN        +5.0%
2025-01-01 02:00    110     +5          NaN        +4.8%
2025-01-01 03:00    115     +5          +15        +4.5%
2025-01-01 04:00    120     +5          +15        +4.3%
```

### 8.4 Complete Feature Engineering Pipeline

```python
def create_time_series_features(df, target_col, window_sizes=[3, 6, 12, 24]):
    """
    Create comprehensive time series features for a target column.
    
    Parameters:
    - df: DataFrame with datetime index
    - target_col: Column name to create features for (e.g., 'aqi')
    - window_sizes: List of rolling window sizes in hours
    
    Returns:
    - DataFrame with all engineered features
    """
    
    # 1. LAG FEATURES
    lag_intervals = [1, 2, 3, 6, 12, 24]
    for lag in lag_intervals:
        df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
    
    # 2. ROLLING STATISTICS
    for window in window_sizes:
        df[f'{target_col}_rolling_mean_{window}'] = \
            df[target_col].rolling(window).mean()
        
        df[f'{target_col}_rolling_std_{window}'] = \
            df[target_col].rolling(window).std()
        
        df[f'{target_col}_rolling_min_{window}'] = \
            df[target_col].rolling(window).min()
        
        df[f'{target_col}_rolling_max_{window}'] = \
            df[target_col].rolling(window).max()
    
    # 3. CHANGE FEATURES
    df[f'{target_col}_change_1h'] = \
        df[target_col] - df[target_col].shift(1)
    
    df[f'{target_col}_change_3h'] = \
        df[target_col] - df[target_col].shift(3)
    
    df[f'{target_col}_change_rate'] = \
        (df[target_col] - df[target_col].shift(1)) / df[target_col].shift(1)
    
    return df

# Usage
df = create_time_series_features(df, target_col='aqi')
print(f"Original features: 1")
print(f"Engineered features: {len([col for col in df.columns if 'aqi' in col])}")
# Output: Engineered features: 26 (1 original + 25 engineered)
```

---

## 9. Feature Engineering Best Practices {#best-practices}

### 9.1 When to Use Each Feature Type

```
┌─────────────────────────────────────────────────────────┐
│              FEATURE SELECTION GUIDE                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  LAG FEATURES                                           │
│  ════════════                                           │
│  Use when: Autocorrelation exists                       │
│  Best for: Short-term predictions (1-24 hours ahead)    │
│  Example: Hourly air quality forecasting                │
│                                                         │
│  ROLLING STATISTICS                                     │
│  ══════════════════                                     │
│  Use when: Trends and patterns matter                   │
│  Best for: Detecting regime changes, volatility         │
│  Example: Identifying pollution episodes                │
│                                                         │
│  CHANGE FEATURES                                        │
│  ═══════════════                                        │
│  Use when: Momentum/direction matters                   │
│  Best for: Detecting sudden changes, alerts             │
│  Example: Early warning systems                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.2 Common Pitfalls and Solutions

#### Pitfall 1: Data Leakage

**Problem**: Using future information in features

```python
# WRONG - Uses future data!
df['aqi_rolling_mean_3'] = df['aqi'].rolling(window=3, center=True).mean()
#                                                     ^^^^^^ BAD!

# CORRECT - Only uses past data
df['aqi_rolling_mean_3'] = df['aqi'].rolling(window=3).mean()
```

#### Pitfall 2: Missing Values

**Problem**: First few rows have NaN for lags/rolling stats

```python
# Check for NaNs
print(df.isnull().sum())

# Solution 1: Drop rows with NaNs
df = df.dropna()

# Solution 2: Forward fill (use with caution!)
df = df.fillna(method='ffill')

# Solution 3: Use partial windows for rolling stats
df['aqi_rolling_mean_3'] = df['aqi'].rolling(window=3, min_periods=1).mean()
```

#### Pitfall 3: Over-Engineering

**Problem**: Creating too many features leads to overfitting

```python
# BAD - Too many features!
for lag in range(1, 100):  # 100 lag features!
    df[f'aqi_lag_{lag}'] = df['aqi'].shift(lag)

# GOOD - Strategic selection
important_lags = [1, 2, 3, 6, 12, 24]  # Only meaningful lags
for lag in important_lags:
    df[f'aqi_lag_{lag}'] = df['aqi'].shift(lag)
```

### 9.3 Feature Importance Analysis

After training, always check which features matter most:

```python
from river import forest

# Train model
model = forest.ARFRegressor(n_models=10)

# After training, check feature importance
# (River doesn't have built-in feature importance, but you can use permutation importance)

# Pseudo-code for understanding:
important_features = {
    'aqi_lag_1': 0.35,          # Most important!
    'aqi_rolling_mean_3': 0.18,
    'aqi_change_1h': 0.12,
    'aqi_lag_24': 0.10,
    'aqi_rolling_std_3': 0.08,
    # ... other features with lower importance
}
```

### 9.4 Domain Knowledge Integration

**General Rule**: Let domain knowledge guide feature engineering.

#### For Air Quality (AQI/PM2.5):

```
Critical Time Scales:
├── 1 hour:  Traffic patterns, immediate emissions
├── 3 hours: Short-term meteorological changes
├── 6 hours: Day/night transitions
├── 12 hours: Half-day patterns
└── 24 hours: Daily cycles, same-time-yesterday

Recommended Features:
✓ Lags at these intervals
✓ Rolling stats for pattern detection
✓ Change rates for alerts
```

#### For Other Domains:

```
Stock Prices:
- Lags: 1 min, 5 min, 15 min, 1 hour, 1 day
- Rolling: Bollinger bands (20-period mean ± 2 std)
- Change: Returns, volatility

Energy Demand:
- Lags: 1 hour, 24 hours, 168 hours (weekly)
- Rolling: 24-hour mean for daily baseline
- Change: Load ramps (sudden increases)

Temperature:
- Lags: 1 hour, 12 hours, 24 hours
- Rolling: 24-hour mean (daily average)
- Change: Temperature gradients
```

---

## 10. Summary and Key Takeaways

### Core Concepts Recap

```
╔════════════════════════════════════════════════════════════╗
║           TIME SERIES FEATURE ENGINEERING                  ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. LAG FEATURES (Historical Values)                       ║
║     → What happened in the past?                           ║
║     → Captures temporal dependencies                       ║
║                                                            ║
║  2. ROLLING STATISTICS (Patterns & Trends)                 ║
║     → What's the pattern over a window?                    ║
║     → Detects trends, volatility, extremes                 ║
║                                                            ║
║  3. CHANGE FEATURES (Momentum & Direction)                 ║
║     → How fast and in which direction?                     ║
║     → Captures dynamics and acceleration                   ║
║                                                            ║
║  TOGETHER: Transform a single value into a rich            ║
║            representation of temporal context              ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

### Why AQI Model Outperforms PM2.5 Model

```
AQI Model:  25 temporal features → Rich context → R² = 0.932
PM2.5 Model: 3 temporal features → Limited context → R² = 0.387

Difference: 8× more information about time-dependent patterns
```

### The Big Picture

**Before Feature Engineering**:
```
Model Input: [AQI_now]
Model Output: AQI_next = ???
Accuracy: Poor (no context)
```

**After Feature Engineering**:
```
Model Input: [
    AQI_now,
    6 lags (what happened before),
    16 rolling stats (patterns and trends),
    3 change rates (momentum and direction)
]
Model Output: AQI_next = 158
Accuracy: Excellent (rich context)
```

### Final Wisdom

> **"In time series prediction, the past is not just data—it's a story. Lag features tell you what happened, rolling statistics reveal the plot, and change features show you where the story is heading."**

---

## Additional Resources

### Mathematical Foundations
- "Time Series Analysis" by James Hamilton
- "Forecasting: Principles and Practice" by Rob Hyndman

### Practical Implementation
- Pandas documentation: `rolling()`, `shift()`, `diff()`
- River library: Online machine learning
- scikit-learn: Feature engineering pipelines

### Domain-Specific Applications
- EPA Air Quality Index Technical Assistance
- WHO Air Quality Guidelines
- Time Series Analysis in Environmental Science

---

**Document Version**: 1.0  
**Date**: December 15, 2025  
**Author**: Self-Healing MLOps Project  
**License**: Educational Use

---

*This document explains the theoretical foundations and practical implementations of time series feature engineering used in the Self-Healing MLOps air quality prediction system.*
