from scapy.all import sniff

def file_write(keys):
    with open("data.txt","a") as file:
        for key in keys:
            file.write(key)

def handle_packet(packet):
    if packet.haslayer("IP"):
        src = packet["IP"].src
        dst = packet["IP"].dst
        print(f"{src} -> {dst}, len={len(packet)}")
        file_write(f"{src} -> {dst}, len={len(packet)}\n")
        if packet.haslayer("UDP"):
            print(f"   UDP {packet['UDP'].sport} -> {packet['UDP'].dport}")
            file_write(f"   UDP {packet['UDP'].sport} -> {packet['UDP'].dport}\n")
            data = bytes(packet["UDP"].payload)
            print(f"   Payload: {data[:50]}...")  # show first 50 bytes
            file_write(f"   Payload: {data}\n")

sniff(iface="en14", prn=handle_packet, store=False)  # Ethernet
# sniff(iface="en0", prn=handle_packet, store=False)   # Wi-Fi
