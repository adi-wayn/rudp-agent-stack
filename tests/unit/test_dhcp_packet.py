import pytest
from common.dhcp_packet import DHCPPacket

def test_dhcp_packet_serialization():
    """Test standard DHCP packet serialization and deserialization."""
    packet = DHCPPacket(
        message_type="OFFER",
        xid=987654321,
        client_mac="AA:BB:CC:DD:EE:FF",
        offered_ip="127.0.0.10",
        lease_time=3600
    )
    
    data = packet.to_bytes()
    assert isinstance(data, bytes)
    
    parsed_packet = DHCPPacket.from_bytes(data)
    assert parsed_packet.message_type == "OFFER"
    assert parsed_packet.xid == 987654321
    assert parsed_packet.client_mac == "AA:BB:CC:DD:EE:FF"
    assert parsed_packet.offered_ip == "127.0.0.10"
    assert parsed_packet.lease_time == 3600

def test_dhcp_packet_defaults():
    """Test DHCP packet with defaults (e.g., DISCOVER)."""
    packet = DHCPPacket(
        message_type="DISCOVER",
        xid=112233,
        client_mac="11:22:33:44:55:66"
    )
    
    data = packet.to_bytes()
    parsed_packet = DHCPPacket.from_bytes(data)
    
    assert parsed_packet.message_type == "DISCOVER"
    assert parsed_packet.offered_ip == ""
    assert parsed_packet.lease_time == 0

def test_dhcp_packet_invalid_bytes():
    """Ensure invalid bytes raise ValueError."""
    with pytest.raises(ValueError):
        DHCPPacket.from_bytes(b"invalid json")
