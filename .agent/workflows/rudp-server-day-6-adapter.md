---
description: Integrate UDP socket layer with RUDP transport state and Agent Server interface.
---

# Workflow: rudp_server_day6_adapter
description: Integrate UDP socket layer with RUDP transport state and Agent Server interface.

goal:
Implement the RUDP Server Adapter that binds a UDP socket,
multiplexes peers, and connects RUDP sender/receiver logic
to the Agent Server transport interface.

steps:

1. Review Architecture:
   - Transport-agnostic design
   - RUDP Sender (cwnd, retransmission, segmentation)
   - RUDP Receiver (buffering, reassembly)
   - Application envelope structure (12B header + payload)

2. Create RUDPServerAdapter class:
   - Initialize UDP socket (AF_INET, SOCK_DGRAM)
   - Bind to AGENT_SERVER_PORT
   - Maintain peer table:
       peers[(ip, port)] → ConnectionPeerState

3. Define ConnectionPeerState:
   - RUDPSender instance
   - RUDPReceiver instance
   - Congestion state (cwnd, ssthresh)
   - Flow control state (rwnd)
   - Timer tracking for retransmissions

4. Implement Event Loop:
   - recvfrom()
   - Identify peer by (ip, port)
   - Create peer state if new
   - Pass segment to peer.receiver
   - Process receiver events:
       - ACK generation
       - Message completion
   - Send outgoing ACKs via sendto()

5. Message Delivery to Agent Server:
   - When full application message reassembled:
       - Forward bytes to Agent Server pipeline
       - Receive response bytes
       - Call peer.sender.send_message(response)
       - Send produced segments via sendto()

6. Retransmission & Timers:
   - Periodic tick loop
   - Check RTO expiration
   - Retransmit oldest unacked segment
   - Update cwnd / ssthresh on timeout
   - Respect rwnd (flow control)

7. Connection Lifecycle:
   - Handle FIN/RST if supported
   - Remove peer state on close
   - Clean timers and buffers

8. Logging:
   - New peer creation
   - Segment received (seq, ack, flags)
   - Retransmission events
   - Message delivery to application
   - Peer cleanup

9. Tests:
   - Single client message roundtrip
   - Multiple concurrent clients
   - Out-of-order delivery
   - Duplicate segment handling
   - Simulated packet loss (retransmission works)

definition_of_done:
- UDP bind/recv/send integrated
- Multiple peers handled correctly
- Full message reassembly working
- Agent Server responds over RUDP
- Retransmissions functional
- No cross-peer state corruption