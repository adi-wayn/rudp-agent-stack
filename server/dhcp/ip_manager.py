import time
from typing import Dict, Optional, Tuple, Set

from common.constants import DHCP_DEFAULT_LEASE_TIME

class IPManager:
    """
    Manages a virtual pool of IP addresses for the simulated DHCP server.
    Tracks leased_ips and manages state transitions (SELECTING, BOUND).
    """

    def __init__(self, start_ip: str = "127.0.0.2", end_ip: str = "127.0.0.254"):
        self.start_ip = start_ip
        self.end_ip = end_ip
        
        # Maps client_mac -> {"ip": str, "xid": int, "expires_at": float, "state": str}
        # Valid states: "SELECTING", "BOUND"
        self.leased_ips: Dict[str, dict] = {}
        
        # Keeps track of IPs currently reserved or bound
        self._allocated_ips: Set[str] = set()

    def _ip_to_int(self, ip: str) -> int:
        parts = list(map(int, ip.split('.')))
        return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]

    def _int_to_ip(self, ip_int: int) -> str:
        return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"

    def _get_next_available_ip(self) -> Optional[str]:
        start = self._ip_to_int(self.start_ip)
        end = self._ip_to_int(self.end_ip)
        
        # Iterate and find first unallocated IP
        for i in range(start, end + 1):
            ip_str = self._int_to_ip(i)
            if ip_str not in self._allocated_ips:
                return ip_str
        return None

    def handle_discover(self, mac: str, xid: int) -> Tuple[Optional[str], int]:
        """
        Handles a DHCP DISCOVER.
        Allocates an IP if new, or returns the existing IP for the MAC.
        Returns: (offered_ip, lease_time). If pool empty, returns (None, 0).
        """
        self.cleanup_expired_leases()
        
        # If client MAC is already known
        if mac in self.leased_ips:
            lease = self.leased_ips[mac]
            
            # If same XID, re-offer the identical state
            if lease["xid"] == xid:
                lease["expires_at"] = time.time() + DHCP_DEFAULT_LEASE_TIME
                return lease["ip"], DHCP_DEFAULT_LEASE_TIME
            
            # If different XID, restart DORA handshake for this MAC using their old IP
            lease["xid"] = xid
            lease["state"] = "SELECTING"
            lease["expires_at"] = time.time() + DHCP_DEFAULT_LEASE_TIME
            return lease["ip"], DHCP_DEFAULT_LEASE_TIME
            
        # Allocate a new IP from the pool
        new_ip = self._get_next_available_ip()
        if not new_ip:
            return None, 0
            
        self._allocated_ips.add(new_ip)
        self.leased_ips[mac] = {
            "ip": new_ip,
            "xid": xid,
            "expires_at": time.time() + DHCP_DEFAULT_LEASE_TIME,
            "state": "SELECTING"
        }
        
        return new_ip, DHCP_DEFAULT_LEASE_TIME

    def handle_request(self, mac: str, xid: int, requested_ip: str) -> bool:
        """
        Handles a DHCP REQUEST.
        Verifies if requested_ip is allocated to this MAC.
        Transitions state to BOUND if valid.
        Returns True if successful (ACK), False if collision/invalid (NACK).
        """
        self.cleanup_expired_leases()
        
        # If we have no record of this MAC, reject
        if mac not in self.leased_ips:
            return False
            
        lease = self.leased_ips[mac]
        
        # IP Collision or mismatched request: client asked for an IP we did not offer them
        if lease["ip"] != requested_ip:
            return False
            
        # Duplicate XID check: Re-ACK if already BOUND
        if lease["xid"] == xid and lease["state"] == "BOUND":
            lease["expires_at"] = time.time() + DHCP_DEFAULT_LEASE_TIME
            return True
            
        # Valid REQUEST
        if lease["state"] == "SELECTING":
            lease["xid"] = xid
            lease["state"] = "BOUND"
            lease["expires_at"] = time.time() + DHCP_DEFAULT_LEASE_TIME
            return True
            
        return False
        
    def cleanup_expired_leases(self):
        """
        Evicts expired addresses from leased_ips pool.
        """
        current_time = time.time()
        expired_macs = []
        
        for mac, lease in self.leased_ips.items():
            if current_time > lease["expires_at"]:
                expired_macs.append(mac)
                
        for mac in expired_macs:
            ip = self.leased_ips[mac]["ip"]
            # Remove from allocated set
            if ip in self._allocated_ips:
                self._allocated_ips.remove(ip)
            # Remove MAC record
            del self.leased_ips[mac]
