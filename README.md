# 🚀 RUDP Agent Stack 🚀

**Multi-Layer Protocol Implementation & Task-Oriented Agent Server**

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)
![Custom Networking](https://img.shields.io/badge/Networking-Custom_OSI_Stack-success.svg?logo=cisco&logoColor=white)
![Reliability](https://img.shields.io/badge/Reliability-100%25_Tested-brightgreen.svg?logo=checkmarx&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-Separation_of_Concerns-purple.svg?logo=awsorganizations&logoColor=white)
![Chaos Engineering](https://img.shields.io/badge/Chaos_Engineering-Survived_40%25_Loss-red.svg?logo=apachejmeter&logoColor=white)

## 📖 Executive Summary

The **RUDP Agent Stack** is a production-grade, distributed system simulator built from the ground up to demonstrate a rigorous, transport-agnostic software architecture. This project implements a fully custom layered network stack, isolating Network Services (DHCP/DNS) and Transport mechanisms (TCP/RUDP) from a high-level **Task-Oriented Agent Server**.

By maintaining a strict Separation of Concerns (SOC), the application logic dynamically executes intelligent, deterministic tasks (like hashing, filtering, and data aggregation) seamlessly over either standard TCP streams or a highly complex, custom **Reliable UDP (RUDP)** protocol built from scratch.

---

## 🏛️ OSI Architecture Mapping

To achieve true decoupling, the system explicitly mirrors the traditional OSI model:

| OSI Layer | System Component | Protocol / Logic Used |
| :--- | :--- | :--- |
| **L7 - Application** | DHCP Server, DNS Server, Agent Server | DHCP (Custom), DNS over HTTP (DoH), Task-Oriented Agent Protocol |
| **L4 - Transport** | RUDP Transceiver / TCP Baseline | Custom RUDP (Selective Repeat, Congestion/Flow Control) or Standard TCP |
| **L3 - Network** | IP Infrastructure | Loopback (`127.0.0.1`) / Virtual Addressing Pool (`127.x.x.x`) |

---

## ✨ Key Technical Features

Our crowning engineering achievements span multiple levels of the system stack:

- 🛡️ **Advanced Custom RUDP (Reliable UDP)**
  - Implements **Selective Repeat** with dynamic Sliding Windows.
  - Full **Congestion Control State Machine** (`SLOW_START`, `CONGESTION_AVOIDANCE`, `FAST_RECOVERY`).
  - Active **Flow Control** using defined high (80%) and low (20%) watermarks (`FC_THROTTLE` / `FC_NORMAL`).
  - Jacobson/Karels algorithm for dynamic **RTO (Retransmission TimeOut)** calculations.

- 🧠 **Intelligent Agent Server**
  - **Idempotency Cache:** A robust application-layer safety net mapping `(client_id, request_id)` to cached responses, ensuring that L4 transport duplications never result in duplicate L7 tool execution (e.g., preventing double file append corruption).
  - **Streaming Execution Paradigm:** Files `<= 256KB` execute entirely in memory. To preserve server hardware allocations, files `> 256KB` mandate zero-copy **Streaming Execution**.

- 🌐 **Virtual Services Infrastructure**
  - Custom DHCP state machine (DORA) issuing Virtual IPs.
  - Seamless local **DNS over HTTP (DoH)** lookup service completely encapsulated within our custom RUDP transport interface.

---

## 🌪️ Chaos Engineering & Extreme Resilience

To scientifically validate the RUDP Transport and the Agent Server's Idempotency Cache, we rely on our built-in `FailureEngine`.

During automated Continuous Integration (CI) and extreme stress testing, the stack successfully executes massive payloads under **Severe Chaos Contexts**:

- **40% Packet Loss:** Actively forces the `cwnd` boundaries and tests exponential backoff timers.
- **50ms Injected Latency:** Validates sequencing and the Jacobson/Karels `DevRTT` calculations.
- **20% Packet Duplication:** Explicitly designed to attack the L7 **Idempotency Cache**, proving mathematical correctness and absolute protection against dirty writes (Append operations).

---

## 💻 How to Run

> [!IMPORTANT]
> **The `sudo` Requirement:** Because our custom DHCP server uses UDP ports 67/68 and the DNS server uses UDP port 53 (which are privileged ports under 1024), users on macOS/Linux **MUST** run the main server and interactive client using `sudo`.

### 1. Launching the Orchestrator (Server Side)

Start the complete sandbox, mounting all background servers (DHCP, DNS, Agent) synchronously.

**Standard TCP Mode (Baseline):**

```bash
sudo python3 -m server --all
```

**Custom RUDP Mode (Recommended):**

```bash
sudo python3 -m server --all --RUDP
```

### 2. Launching the Interactive Client

Engage with the comprehensive Terminal UI to test individual protocol boundaries. You can acquire virtual leases via DHCP, resolve DNS, execute standard file operations, and dispatch distributed tasks.

**Standard Launch:**

```bash
sudo python3 -m client
```

**Chaos Injection Launch:**

You can directly inject the `FailureEngine` from the CLI to test resilience under harsh network conditions:

```bash
sudo python3 -m client --loss 20 --latency 50 --dup 10
```

### 3. Automated CI/CD & Chaos Testing

Prove the resilience of the custom stack locally without human intervention. Ensure the server is not running, as these execute their own background threads.

> [!NOTE]
> The automated scripts dynamically negotiate unprivileged ports (e.g., 6767, 8081) in the background. Because they avoid the standard privileged ports, they uniquely **DO NOT require `sudo`**.

**Standard E2E Verification (20% packet loss):**

```bash
python3 -m scripts.auto_e2e_runner
```

**⚠️ Extreme Chaos Stress Test (40% loss, 50ms latency, 20% duplicate rate):**

```bash
python3 -m scripts.extreme_stress_test
```

*(This will rigorously loop heavy `UPLOAD`, `APPEND`, `TASK`, and `GET` workloads, mathematically verifying byte-for-byte integrity upon completion.)*

---
*Architected to strictly satisfy the System Specification parameters.*
