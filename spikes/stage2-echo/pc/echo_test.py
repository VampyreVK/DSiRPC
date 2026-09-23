import socket
import threading

LISTEN_PORT = 4242

def listen(sock):
	while True:
		data, addr = sock.recvfrom(1024)
		print(f"\n[from {addr}] {data.decode(errors='replace')}")

def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(("0.0.0.0", LISTEN_PORT))

	print(f"Listening on port {LISTEN_PORT}. Waiting for the DSi's startup ping...")
	data, dsi_addr = sock.recvfrom(1024)
	print(f"Got startup ping from {dsi_addr}: {data.decode(errors='replace')}")

	threading.Thread(target=listen, args=(sock,), daemon=True).start()

	print(f"\nSending to {dsi_addr[0]}:{dsi_addr[1]} from here on.")
	print("Type a message and press Enter to send it to the DSi.")
	print("Type EXIT to tell the DSi to stop listening. Ctrl+C to quit this script.\n")

	while True:
		msg = input("> ")
		if msg:
			sock.sendto(msg.encode(), dsi_addr)

if __name__ == "__main__":
	main()
