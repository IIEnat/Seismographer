import socket

# Bind to port 18000 (or whichever your instrument sends to)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP example
sock.bind(("0.0.0.0", 18000))
sock.listen()

print("Listening for connections on port 18000...")

while True:
    conn, addr = sock.accept()
    print("Connected by", addr)
    data = conn.recv(1024)
    print("Received:", data)
