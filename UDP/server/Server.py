import socket
import os
import threading
import struct

BUFFER_SIZE = 1024
TIMEOUT = 30  # Seconds
PORT = 9000

file_list = {}
file_lock = threading.Lock()

def create_packet(seq_num, ack_num, data, ack=False):
    checksum = sum(data) % 256
    ack_flag = 1 if ack else 0
    header = struct.pack('!I I B B', seq_num, ack_num, checksum, ack_flag)
    return header + data

def verify_packet(packet):
    if len(packet) < 10:
        return False, None, None, None, None
    seq_num, ack_num, checksum, ack_flag = struct.unpack('!I I B B', packet[:10])
    data = packet[10:]
    return checksum == sum(data) % 256, seq_num, ack_num, data, ack_flag

def reliable_receive(server_socket):
    while True:
        try:
            server_socket.settimeout(TIMEOUT)
            packet, addr = server_socket.recvfrom(BUFFER_SIZE)
            valid, seq_num, ack_num, data, ack_flag = verify_packet(packet)
            if valid:
                ack_packet = create_packet(seq_num, ack_num, b'', ack=True)
                server_socket.sendto(ack_packet, addr)
                return data, addr
        except socket.timeout:
            print("Timeout, waiting for packet")
            continue
        except BlockingIOError:
            continue
        except OSError as e:
            print(f"Socket error during reliable_receive: {e}")
            return None, None
        
WINDOW_SIZE = 20

def reliable_send(server_socket, addr, data, base_seq_num):
    next_seq_num = base_seq_num
    window = []
    acked = set()
    data_chunks = [data[i:i + BUFFER_SIZE - 10] for i in range(0, len(data), BUFFER_SIZE - 10)]

    while base_seq_num < len(data_chunks):
        while next_seq_num < base_seq_num + WINDOW_SIZE and next_seq_num < len(data_chunks):
            if (next_seq_num == len(data_chunks) - 1):
                packet = create_packet(next_seq_num, 0, data_chunks[next_seq_num], ack=True)
            else:
                packet = create_packet(next_seq_num, 0, data_chunks[next_seq_num])
            server_socket.sendto(packet, addr)
            window.append(packet)
            next_seq_num += 1

        try:
            server_socket.settimeout(TIMEOUT)
            ack, _ = server_socket.recvfrom(BUFFER_SIZE)
            
            valid, ack_seq_num, _, _, ack_flag = verify_packet(ack)
            if valid and ack_flag == 1:
                acked.add(ack_seq_num)
                while base_seq_num in acked:
                    base_seq_num += 1
                    window.pop(0)
        except socket.timeout:
            print("Timeout, retransmitting window")
            for packet in window:
                server_socket.sendto(packet, addr)
        except OSError as e:
            print(f"Socket error during reliable_send: {e}")
            break 
            
def send_file_list(client_socket, addr):
    with file_lock:
        response = "\n".join([f"{file} {size}" for file, size in file_list.items()])
        reliable_send(client_socket, addr, response.encode(), 0)

def handle_download_request(client_socket, request, addr):
    parts = request.split() # DOWNLOAD file_name chunk_id start end
    if len(parts) != 5:
        return
    _, file_name, chunk_id, start, end = parts
    start, end = int(start), int(end)
    if(file_name in file_list):
        # Create a new socket for this download session
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as download_socket:
            send_file_chunk(download_socket, addr, file_name, start, end, int(chunk_id))

def send_file_chunk(client_socket, addr, file_name, start, end, chunk_id):
    try:
        with open(file_name, 'rb') as f:
            f.seek(start)
            data = f.read(end - start + 1)  # Leave space for the header
            #no need to use chunk ID
            reliable_send(client_socket, addr, data, 0)
    except Exception as e:
        print(f"Error sending file chunk {file_name}: {e}")
    

def load_file_list():
    global file_list
    with open('input.txt', 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                file_name, size_str = parts
                file_list[file_name] = size_str

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', PORT))
    print(f"Server listening on port {PORT}")
    try:
        while True:
            try:
                # request, addr = server_socket.recvfrom(BUFFER_SIZE)
                # valid, seq_num, ack_num, data, ack_flag = verify_packet(request)
                # reliable_send(server_socket, addr, b"", 0)
                data, addr = reliable_receive(server_socket)
                data = data.decode().strip()
                print(f"Request: {data}")
                if data == "LIST":
                    load_file_list()
                    send_file_list(server_socket, addr)
                elif data.startswith("QUIT"):
                    print(f"Client {addr} disconnected.")
                    break                    
                else:
                    while True:
                        try:
                            request, addr = reliable_receive(server_socket)
                            request = request.decode()
                            if request.startswith("DOWNLOAD"):
                                handle_download_request(server_socket, request, addr)
                            else:
                                break
                        except OSError as e:
                            print(f"Socket error during reliable_receive: {e}")
                            break
            except OSError as e:
                print(f"Socket error: {e}")
                break
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()