# RUDP Agent Stack

## End-to-End Multi-Layer Network Stack with Custom Reliable UDP and Agent-Based Task Execution.

### Architecture Overview
This project implements a custom network stack featuring a Reliable UDP (RUDP) transport layer and an Agent-based Application protocol. It includes a simulated network environment with failure injection (latency, drop, reorder) to validate the robustness of the transport protocol.

### Folder Structure
- **client/**: Client-side implementations (DHCP, DNS, Agent, RUDP, TCP).
- **server/**: Server-side implementations (DHCP, DNS, Agent, RUDP, TCP).
- **common/**: Shared utilities, constants, protocols, and error definitions.
- **simulations/**: Failure engine and network simulation tools.
- **tests/**: Unit and integration tests.

### Components

#### Transport Layer
- **TCP**: Baseline implementation for comparison.
- **RUDP**: Custom Reliable UDP protocol implementing:
    - Three-way handshake
    - Congestion Control (AIMD/Slow Start)
    - Flow Control (Sliding Window)
    - Retransmissions (RTO, Fast Retransmit)

#### Agent Execution Model
- Clients connect to the Agent Server to request task execution.
- Tasks are defined by payloads and executed via handlers.
- Supports file transfer (PUT/GET) and command execution.

#### DHCP + DNS
- Custom DHCP and DNS servers to manage rudimentary service discovery and addressing within the simulation scope.

### Development Roadmap
- [ ] Skeleton & Scaffolding
- [ ] Common Protocol Definitions
- [ ] Failure Engine Implementation
- [ ] RUDP Transport Layer
- [ ] Agent Protocol Layer
- [ ] Application Logic & CLI

### How to Run
*(Placeholder commands)*
```bash
# Install dependencies
pip install -r requirements.txt

# Run Unit Tests
pytest tests/unit

# Run Server
python -m server.agent_server

# Run Client
python -m client.agent_client
```

### Contribution Guidelines
- Follow PEP8.
- Ensure type hints are present.
- Write tests for new features.
