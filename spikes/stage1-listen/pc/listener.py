import socket

PORT = 4242

def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(("0.0.0.0", PORT))
	print(f"Listening for UDP packets on port {PORT}...")

	while True:
		data, addr = sock.recvfrom(1024)
		print(f"Received from {addr}: {data.decode(errors='replace')}")

if __name__ == "__main__":
	main()
