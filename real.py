import socket

HOST = '0.0.0.0'  # listen on all available interfaces
PORT = 57329   # the port the seismometers send to
BUFFER_SIZE = 1024

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:  # UDP is common
    s.bind((HOST, PORT))
    print(f"Listening on {HOST}:{PORT} for seismometer data...")

    while True:
        data, addr = s.recvfrom(BUFFER_SIZE)
        print(f"From {addr}: {data}")
        with open("seismo_data.txt", "a") as f:
            f.write(f"{addr}: {data}\n")
