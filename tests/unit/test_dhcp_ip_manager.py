import time
import pytest
from server.dhcp.ip_manager import IPManager
from common.constants import DHCP_DEFAULT_LEASE_TIME

def test_ip_manager_dora_happy_path():
    manager = IPManager()
    mac = "00:11:22:33:44:55"
    xid = 1001

    # SIMULATE [D]ISCOVER
    offered_ip, lease_time = manager.handle_discover(mac, xid)
    assert offered_ip == "127.0.0.2"
    assert lease_time == DHCP_DEFAULT_LEASE_TIME
    assert manager.leased_ips[mac]["state"] == "SELECTING"
    assert "127.0.0.2" in manager._allocated_ips

    # SIMULATE [R]EQUEST
    success = manager.handle_request(mac, xid, offered_ip)
    assert success is True
    assert manager.leased_ips[mac]["state"] == "BOUND"

def test_ip_manager_duplicate_xid():
    manager = IPManager()
    mac = "AA:BB:CC:DD:EE:FF"
    xid = 2002

    # First discover
    manager.handle_discover(mac, xid)
    
    # Duplicate discover (e.g. lost offer packet)
    offered_ip, lease_time = manager.handle_discover(mac, xid)
    assert offered_ip == "127.0.0.2"
    assert manager.leased_ips[mac]["state"] == "SELECTING"

    # Request
    manager.handle_request(mac, xid, offered_ip)

    # Duplicate Request (e.g. lost ACK packet)
    success = manager.handle_request(mac, xid, offered_ip)
    assert success is True  # Re-ACK behavior
    assert manager.leased_ips[mac]["state"] == "BOUND"

def test_ip_manager_collision_nack():
    manager = IPManager()
    mac1 = "M1:11:11:11:11:11"
    mac2 = "M2:22:22:22:22:22"
    
    # M1 discovers and gets 127.0.0.2
    manager.handle_discover(mac1, 3003)
    
    # M2 discovers and gets 127.0.0.3
    offered_m2, _ = manager.handle_discover(mac2, 4004)
    assert offered_m2 == "127.0.0.3"

    # M2 requests IP belonging to M1 (Collision scenario)
    success = manager.handle_request(mac2, 4004, "127.0.0.2")
    assert success is False  # Must send NACK

def test_ip_manager_pool_exhaustion():
    manager = IPManager(start_ip="127.0.0.2", end_ip="127.0.0.3")
    
    mac1 = "A1"
    mac2 = "A2"
    mac3 = "A3"
    
    # Allocate all IPs
    ip1, _ = manager.handle_discover(mac1, 1)
    ip2, _ = manager.handle_discover(mac2, 2)
    
    assert ip1 == "127.0.0.2"
    assert ip2 == "127.0.0.3"
    
    # Exhaustion
    ip3, _ = manager.handle_discover(mac3, 3)
    assert ip3 is None

def test_ip_manager_lease_cleanup(monkeypatch):
    manager = IPManager()
    mac = "C1"
    
    manager.handle_discover(mac, 999)
    manager.handle_request(mac, 999, "127.0.0.2")
    
    assert "127.0.0.2" in manager._allocated_ips
    
    # Fast forward time to past expiration (DHCP_DEFAULT_LEASE_TIME is 3600)
    original_time_fn = time.time
    monkeypatch.setattr(time, "time", lambda: original_time_fn() + 4000)
    
    manager.cleanup_expired_leases()
    assert mac not in manager.leased_ips
    assert "127.0.0.2" not in manager._allocated_ips
