# ☁️ Cloud-FinOps Orchestrator

A **real-time Multi-Region Network Operations Center (NOC)** that intelligently automates AWS infrastructure.
The orchestrator continuously monitors infrastructure across multiple AWS regions and makes automated routing decisions based on the following priority:

> **Health → Performance → Cost**

This ensures maximum uptime while optimizing operational expenses and network latency.

---


# Architecture

```
                    Next.js Dashboard
                           │
                           ▼
                    Flask Backend API
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
     Terraform          AWS Boto3       Decision Engine
        │                  │                  │
        ▼                  ▼                  ▼
   EC2 + S3 Backend   Spot Pricing     Health > Latency > Cost
        │
        ▼
 GitHub Actions CI/CD
        │
        ▼
      n8n Webhook
        │
        ▼
 Google Sheets Audit Log
```

---

## Tech Stack

  | Category | Technology |
  | :--- | :--- |
  | **Frontend** | Next.js, Vercel |
  | **Backend Engine** | Python (Flask) |
  | **Agent Orchestration** | LangChain, LangGraph |
  | **Cloud Platform** | Amazon Web Services (EC2, S3 Remote State) |
  | **Infrastructure** | Terraform |
  | **Cloud SDK** | Boto3 |
  | **CI/CD** | GitHub Actions |
  | **Automation** | n8n, Google Sheets API |

---

## Key Features

### 1. Agentic AI Orchestration

- **Intelligent Workflows:** Integrates **LangGraph** to construct stateful, multi-agent workflows capable of handling complex decision-making beyond linear execution.
- **Smart Interaction:** Utilizes **LangChain** for LLM integration and tool calling, enabling the orchestrator to dynamically respond to system state changes and natural language inputs with advanced reasoning capabilities.

---

### 2. Health-Aware Routing & Multi-Region High Availability

- **Active Constraints:** Continuously evaluates cloud health alongside cost and performance metrics, with routing decisions always constrained by infrastructure health.
- **Failover Logic:** Manages redundant instances across:
  - **Asia-South-1 (Mumbai)**
  - **US-East-1 (Virginia)**
- **Automatic Failover:** If a region becomes **Unreachable**, traffic is immediately redirected to the standby region.
- **Priority Rule:** Health always overrides cost and latency to maximize service availability.

---

### 3. Live Audit & Automation Pipeline

- **Webhook Integration:** Every infrastructure mode change triggers an HTTP POST webhook from the Flask backend to a local **n8n** workflow.
- **Cloud Sync:** Using secure **OAuth2** authentication, n8n captures the JSON payload and appends:
  - Event
  - Details
  - Timestamp
  directly into a live **Google Spreadsheet**.
- **Zero-Latency Logging:** Logging is fully decoupled from the backend, ensuring external API calls never slow down application performance.

---

### 4. Interactive NOC Dashboard

- **Dynamic Interface:** Built with **Next.js** for real-time infrastructure monitoring.
- **Optimized Layout:** Carefully structured to prevent data clutter during operational monitoring.
- **Visual Metrics:** Includes a dedicated real-time latency graph positioned below the Profit Mode toggle for instant visual analysis.

---

### 5. Priority-Weighted Decision Engine

- **Conflict Resolution:** Decisions follow the strict hierarchy:

  ```
  Health
      ↓
  Performance
      ↓
  Cost
  ```

- **Latency Mode:** Optimizes routing using real-time ICMP telemetry.
- **Profit Mode:** Minimizes cloud costs using live AWS Spot Instance pricing via **Boto3**.

---

### 6. Advanced CI/CD & State Management

- **Continuous Deployment:** Infrastructure is automatically provisioned through **GitHub Actions** on every repository push.
- **Nuclear Destroy Mode:** Provides an automated workflow to safely destroy all cloud resources after testing, preventing unnecessary AWS charges.
- **Hybrid State Management:** Uses an **S3 Remote Backend** for persistent Terraform state storage and locking across local and CI/CD environments.

---

# Quick Start

## 1. Clone Repository

```bash
git clone https://github.com/your-username/cloud-finops-orchestrator.git

cd cloud-finops-orchestrator
```

---

## 2. Provision Infrastructure

Initialize Terraform.

```bash
terraform init
```

Deploy AWS resources.

```bash
terraform apply
```

---

## 3. Launch Backend

Start the Flask server.

```bash
python app.py
```

Ensure your **n8n workflow** is also running.

---

## 4. Run Frontend

```bash
npm install

npm run dev
```
