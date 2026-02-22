import sys
import os
import time
import socket
import threading
import traceback

# Using absolute path to artifacts directory for logging
LOG_FILE = r"C:\Users\Halel\.gemini\antigravity\brain\1ed7d698-fe16-44a6-bf68-42080ef7148a\debug_log.txt"

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except:
        pass
    print(msg)

if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
    except:
        pass

log(f"DEBUG: Current directory: {os.getcwd()}")
log(f"DEBUG: sys.path: {sys.path}")

try:
    log("DEBUG: Importing RUDP modules...")
    # Add CWD to sys.path explicitly
    sys.path.append(os.getcwd())
    from server.transport.rudp_adapter import RUDPServerAdapter
    from common.app_envelope import encode_message, decode_header, HEADER_SIZE
    log("DEBUG: Imports successful.")
except Exception as e:
    log(f"DEBUG: Import failed: {e}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
    except:
        pass
    sys.exit(1)

def mock_on_message(client_id, data):
    log(f"[CALLBACK] Received message from {client_id}: {data.hex()}")
    try:
        header = decode_header(data[:HEADER_SIZE])
        resp = encode_message(header.opcode, header.request_id, b"PONG")
        log(f"[CALLBACK] Returning response: {resp.hex()}")
        return resp
    except Exception as e:
        log(f"[CALLBACK] Error in callback: {e}")
        return None

def run_debug():
    port = 9999
    try:
        adapter = RUDPServerAdapter(port=port)
    except Exception as e:
        log(f"[MAIN] Failed to create adapter: {e}")
        return
    
    log(f"[MAIN] Starting server on {port}...")
    server_thread = threading.Thread(target=adapter.serve, args=(mock_on_message,), daemon=True)
    server_thread.start()
    
    time.sleep(2)
    
    log("[MAIN] Creating client socket...")
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.settimeout(5)
    
    payload = b"PING"
    ping_msg = encode_message(0xFF, 123, payload)
    
    log(f"[MAIN] Sending PING ({ping_msg.hex()}) to 127.0.0.1:{port}")
    try:
        client_sock.sendto(ping_msg, ("127.0.0.1", port))
    except Exception as e:
        log(f"[MAIN] Send failed: {e}")
        return
    
    try:
        log("[MAIN] Waiting for response...")
        data, addr = client_sock.recvfrom(1024)
        log(f"[MAIN] Received response from {addr}: {data.hex()}")
        header = decode_header(data[:HEADER_SIZE])
        log(f"[MAIN] Success! Request ID: {header.request_id}, Payload: {data[HEADER_SIZE:]}")
    except socket.timeout:
        log("[MAIN] ERROR: Timed out waiting for response")
    except Exception as e:
        log(f"[MAIN] ERROR: {e}")
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except:
            pass
    finally:
        log("[MAIN] Closing adapter and socket...")
        adapter.close()
        client_sock.close()
        time.sleep(1)
    log("[MAIN] Done.")

if __name__ == "__main__":
    run_debug()
