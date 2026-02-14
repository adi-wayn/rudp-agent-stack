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


### Day 1 Smoke Test (TCP PING/PONG)
To verify the base TCP transport and 12-byte Application Envelope framing:

1. **Start the TCP Server**:
   ```bash
   python -m server.transport.tcp_server
   ```
   *Output should show: `[TCP-Server] TCP Server listening on 127.0.0.1:8080`*

2. **Run the TCP Client** (in a new terminal):
   ```bash
   python -m client.transport.tcp_client
   ```

**Expected Result**:
- Client connects and sends `OP_PING` (0xFF).
- Server logs the request and responds with `OP_PONG` (0xFE).
- Client validates the response and logs: `Test PASSED: Received PONG.`

### Contribution Guidelines
- Follow PEP8.
- Ensure type hints are present.
- Write tests for new features.

### Day 2 Smoke Test
This test validates the Core Agent Server pipeline, including the `LIST` opcode, Idempotency Cache, and Policy Guard validation.

1. **Start the Agent Server** (using the Day 2 integration wrapper):
   ```bash
   python tests/integration/run_day2_server.py
   ```
   *Output should show: `[Day2Server] Day 2 Agent Server listening on 127.0.0.1:8080`*

2. **Run the Manual LIST Test**:
   ```bash
   python tests/integration/manual_test_list.py
   ```

**Expected Output**:
```text
Connected to 127.0.0.1:8080
Sent LIST request
Received Header: Op=5 Len=...
Files in sandbox: ['hello.txt']
```

**Validates**:
- **12-byte header integrity**: Verified by correct decoding.
- **TCP framing correctness**: Payload boundaries respected.
- **Dispatcher routing**: Opcode 5 routed to `handle_list`.
- **PolicyGuard enforcement**: Sandbox access logic active.
- **Idempotency behavior**: Cache checks performed.

> **Note**: This smoke test verifies the application-layer pipeline before Reliable UDP integration (Day 6).