"""
Common System Constants.
Derived strictly from docs/specs/System_Specification.md.
"""

# ==============================================================================
# 8.1 Application Layer Message Envelope
# ==============================================================================
PROTOCOL_VERSION = 1
HEADER_SIZE = 12  # Fixed 12-byte header

# ==============================================================================
# 8.2 Opcode Numeric Definitions
# (Assigned sequentially as spec contained placeholders)
# ==============================================================================
OP_PUT_META = 0x01
OP_PUT_CHUNK = 0x02
OP_GET = 0x03
OP_APPEND = 0x04
OP_LIST = 0x05

# Internal Opcodes
OP_UPLOAD = 0xFF
OP_TASK_SEARCH_REPORT = 0x10
OP_TASK_FILTER_LINES = 0x11
OP_TASK_HASH_AND_STORE = 0x12

# ==============================================================================
# 8.7 Implementation Constants
# ==============================================================================
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MiB
MSS = 1200  # bytes
MAX_RWND = 64  # segments

# Flow Control Watermarks
# Defined as percentages of buffer usage
HIGH_WATERMARK = 0.80  # 80%
LOW_WATERMARK = 0.20   # 20%

# Congestion Control
INITIAL_CWND = 1 * MSS
INITIAL_SSTHRESH = 64 * MSS
MAX_RETRIES = 5

# ==============================================================================
# 8.16.5 Timer Parameters
# ==============================================================================
INITIAL_RTO = 0.5  # seconds (500ms)
ALPHA = 0.125      # (1 - 0.125) weighting
BETA = 0.25        # (1 - 0.25) weighting
MAX_RTO = 4.0      # seconds

# ==============================================================================
# Miscellaneous
# ==============================================================================
# Derived from MAX_FILE_SIZE for Day 1 simplicity, 
# though spec allows segmented transfer for > 64KB.
MAX_PAYLOAD_LEN = MAX_FILE_SIZE 

# Defined in 8.14 (implied) and 1. Executive Summary
LOOPBACK_IP = "127.0.0.1"
DHCP_SERVER_PORT = 67
DHCP_CLIENT_PORT = 68
DNS_SERVER_PORT = 53
AGENT_SERVER_PORT = 8080  # Common convention, distinct from system ports
