#  Cloud-FinOps Orchestrator

A real-time Multi-Region **Network Operations Center (NOC)** that automates AWS infrastructure through a triple-constraint engine: Cost (FinOps), Performance (Latency), and Availability (Health).

---


##  Tech Stack

| Category           | Technology                                 |
| ------------------ | ------------------------------------------ |
|  Cloud Platform  | Amazon Web Services (EC2, S3 Remote State) |
|  Infrastructure | Terraform                                  |
|  Backend Engine  | Python (Flask)                             |
|  Cloud SDK       | Boto3                                      |
|  CI/CD           | GitHub Actions                             |

---

##  Key Features

###  1. Multi-Region High Availability (HA)

* Proactively manages redundant instances across Asia-South-1 (Mumbai) and US-East-1 (Virginia) to eliminate single points of failure.



###  2. Health-Aware Routing

* Integrated Health Check Heartbeat monitoring ICMP connectivity.
*  **Failover Logic**:   If a region becomes "Unreachable," the orchestrator triggers an immediate failover to the standby region.
  
*  **Priority Rule** :   This bypasses cost or latency preferences to ensure 100% service uptime.



###  3. Hybrid State Management

* Utilizes an S3 Remote Backend for persistent infrastructure state and state locking, ensuring consistency across local and CI/CD environments.



###  4. Auto-Reconciliation Engine

* Automatically detects:

  * Public IP changes
  * Manual AWS instance reboots



###  5. Priority-Weighted Decision Engine

* The system resolves routing conflicts using a strict hierarchy: Health > Performance > Cost.

*  **Latency Mode**:  Optimizes the network path based on real-time ICMP telemetry.
  
*  **Profit Mode** :  Minimizes cloud burn-rate using live Spot Instance market data via Boto3.



###  6. GitHub Actions CI/CD

*  **Continuous Deployment**:   Infrastructure auto-provisioned on every push.
  
*  **Nuclear Destroy Mode**:

   *  Manual workflow to instantly destroy all resources
   *  Prevents unexpected cost overruns

---

##  Quick Start

###  Provision Infrastructure

```bash
terraform init
terraform apply
```



###  Launch NOC Dashboard

```bash
python app.py
```



###  Automate Lifecycle

* Push code changes to GitHub
* CI/CD pipeline will automatically:

  * Deploy infrastructure
  * Sync state
  * Apply updates

