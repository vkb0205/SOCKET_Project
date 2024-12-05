
import socket
import threading
import os
import struct
import time

BUFFER_SIZE = 1024
TIMEOUT = 2  # Seconds

#1. Reliable Data Transfer Mechanism
#Sequence Numbers: Attach a sequence number to each packet. The client ensures packets are processed in order.
#Acknowledgements (ACKs): The client sends an ACK for each received packet. If the server doesn't receive an ACK, it retransmits the packet.
#Checksums: Include a checksum for error detection.
#Timeouts: Set a timeout for retransmission if an ACK isn't received

"""
Checksum: 
- A checksum is a value that represents the number of bits in a transmission message and is used by IT professionals 
to detect high-level errors within data transmissions.
- If the checksum value the user calculates is even slightly different from the checksum value of the original file, it 
can alert all parties in the transmission that the file was corrupted or tampered with by a third party, such as in 
the case of malware.
"""


def create_packet(seq_num, data):
    checksum = sum(data) % 256
    """
    sum(data): Computes the sum of all the bytes in the data.
    % 256: Takes the modulo 256 of the sum to ensure the checksum is a single byte (0-255). This checksum is used 
    for error detection.
    """
    header = struct.pack('!I B', seq_num, checksum)  # Sequence number (4 bytes) + checksum (1 byte)
    """
    struct.pack('!I B', seq_num, checksum): Uses the struct module to pack the sequence number and checksum into a binary format.
        '!I B': The format string specifies the data types and their sizes:
        '!': Network byte order (big-endian).
        'I': Unsigned integer (4 bytes) for the sequence number.
        'B': Unsigned char (1 byte) for the checksum.
    """
    return header + data

def verify_packet(packet):
    if len(packet) < 5:
        return False, None, None  # Packet is too short to be valid
    seq_num, checksum = struct.unpack('!I B', packet[:5])
    data = packet[5:]
    return checksum == sum(data) % 256, seq_num, data
    """The function returns a tuple containing:
        1. A boolean indicating whether the checksum is valid.
        2. The sequence number.
        3. The data.
    """

def reliable_send(server_socket, addr, data, seq_num):
    packet = create_packet(seq_num, data)
    while True:
        server_socket.sendto(packet, addr)
        try:
            server_socket.settimeout(TIMEOUT)
            ack, _ = server_socket.recvfrom(BUFFER_SIZE)
            if len(ack) == 4:  # Ensure the ack is 4 bytes long
                ack_seq_num = struct.unpack('!I', ack)[0]
                if ack_seq_num == seq_num:
                    break  # ACK received, send next packet
        except socket.timeout:
            continue  # Retransmit
        except OSError:
            break  # Socket closed, exit loop

def reliable_receive(server_socket):
    while True:
        try:
            server_socket.settimeout(TIMEOUT)
            packet, addr = server_socket.recvfrom(BUFFER_SIZE)
            valid, seq_num, data = verify_packet(packet)
            if valid:
                ack = struct.pack('!I', seq_num)
                server_socket.sendto(ack, addr)
                return data, addr
        except socket.timeout:
            continue  # Wait for the next packet
        except OSError:
            break  # Socket closed, exit loop



def handle_chunk(addr, filename, chunk_id, start, end, server_socket, seq_num_counter):
    try:
        with open(filename, 'rb') as f:
            f.seek(start)
            bytes_to_send = end - start + 1
            seq_num = seq_num_counter

            while bytes_to_send > 0:
                chunk = f.read(min(BUFFER_SIZE - 5, bytes_to_send))
                if not chunk:
                    break

                reliable_send(server_socket, addr, chunk, seq_num)
                seq_num += 1
                bytes_to_send -= len(chunk)
    except Exception as e:
        print(f"Error handling chunk: {e}")


def load_file_list(file_path):
    file_list = {}
    with open(file_path, 'r') as f:
        for line in f:
            name, size = line.strip().split()
            file_list[name] = size
    return file_list


def main():
    HOST = "0.0.0.0"
    PORT = 9000
    FILE_LIST_PATH = "input.txt"

    file_list = load_file_list(FILE_LIST_PATH)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((HOST, PORT))
    print(f"UDP Server listening on {HOST}:{PORT}")

    seq_num_counter = 0

    try:
        while True:
            data, addr = reliable_receive(server_socket)
            print(f"\nConnected by {addr}")
            request = data.decode().strip().split()
            print(f"Request: {request}")
            command = request[0]
            if command == "LIST":
                response = '\n'.join([f"{name} {size}" for name, size in file_list.items()])
                reliable_send(server_socket, addr, response.encode(), seq_num_counter)
                seq_num_counter += 1
            #DOWNLOAD {file_name} {chunk_id} {start} {end}
            elif command == "DOWNLOAD" and len(request) == 5:
                filename, chunk_id, start, end = request[1], int(request[2]), int(request[3]), int(request[4])
                if filename not in file_list:
                    reliable_send(server_socket, addr, b"File not found", seq_num_counter)
                    seq_num_counter += 1
                    continue
                threading.Thread(target=handle_chunk, args=(addr, filename, chunk_id, start, end, server_socket, seq_num_counter)).start()
            elif command == 'DOWNLOADING':
                    print(f"Downloading in progress")
                    # Handle DOWNLOADING protocol
                    reliable_send(server_socket, addr, b'Downloading in progress\n', seq_num_counter)
                    seq_num_counter += 1

            elif command == 'QUIT':
                print(f"Connection closed\n")
                # Handle END protocol
                reliable_send(server_socket, addr, b'Connection closed\n', seq_num_counter)
                seq_num_counter += 1
                break
            else:
                reliable_send(server_socket, addr, b'Invalid request\n', seq_num_counter)
                seq_num_counter += 1
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
