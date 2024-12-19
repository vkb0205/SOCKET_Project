import socket
import os
import time
import threading
import sys
import struct
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

WINDOW_SIZE = 5
BUFFER_SIZE = 1024
TIMEOUT = 10  # Seconds

# RDT
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

def reliable_send(server_socket, addr, data, seq_num):
    ack_num = 0
    packet = create_packet(seq_num, ack_num, data)
    while True:
        try:
            server_socket.sendto(packet, addr)
            server_socket.settimeout(TIMEOUT)
            ack, _ = server_socket.recvfrom(BUFFER_SIZE)
            valid, ack_seq_num, ack_num, _, ack_flag = verify_packet(ack)
            if valid and ack_flag == 1 and ack_seq_num == seq_num:
                break
        except socket.timeout:
            print("Timeout, retransmitting packet")
            continue
        except OSError as e:
            print(f"Socket error during reliable_send: {e}")
            break

# def reliable_receive(server_socket):
#     while True:
#         try:
#             server_socket.settimeout(TIMEOUT)
#             packet, addr = server_socket.recvfrom(BUFFER_SIZE)
#             valid, seq_num, ack_num, data, ack_flag = verify_packet(packet)
#             if valid:
#                 ack_packet = create_packet(seq_num, ack_num, b'', ack=True)
#                 server_socket.sendto(ack_packet, addr)
#                 return data, addr
#         except socket.timeout:
#             print("Timeout, waiting for packet")
#             continue
#         except BlockingIOError:
#             continue
#         except OSError as e:
#             print(f"Socket error during reliable_receive: {e}")
#             return None, None

def reliable_receive(server_socket):
    expected_seq_num = 0
    received_data = b''
    while True:
        try:
            server_socket.settimeout(TIMEOUT)
            packet, addr = server_socket.recvfrom(BUFFER_SIZE)
            valid, seq_num, _, data, ack_flag = verify_packet(packet)
            if valid and seq_num == expected_seq_num:
                    received_data += data
                    ack_packet = create_packet(seq_num, 0, b'', ack=True)
                    server_socket.sendto(ack_packet, addr)
                    expected_seq_num += 1
                    if (ack_flag == 1):
                        return received_data, addr
            else:
                ack_packet = create_packet(expected_seq_num - 1, 0, b'', ack=True)
                server_socket.sendto(ack_packet, addr)
        except socket.timeout:
            print("Timeout, waiting for packet")
            continue
        except BlockingIOError:
            continue
        except OSError as e:
            print(f"Socket error during reliable_receive: {e}")
            return None, None
    

# Convert size string to bytes
def convert_to_bytes(size_str):
    size_str = size_str.upper()
    if size_str.endswith('B'):
        return int(size_str[:-1])
    elif size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        raise ValueError(f"Unknown size format: {size_str}")

file_lists = []

# Safely add files with a lock
file_lock = threading.Lock()

import re  # For regex normalization

def read_new_files(sock, host, port):
    global file_lists
    try:
        # Request file list from server
        reliable_send(sock, (host, port), "LIST\n".encode(), 0)
        print("Sent LIST request to server")
        response, _ = reliable_receive(sock)
        
        if response is None:
            return file_lists
        
        response = response.decode().strip()
        file_list = response.split('\n')
        
        with file_lock:
            for file_info in file_list:
                file_info = file_info.strip()  # Remove leading/trailing whitespace
                file_info = re.sub(r'\s+', ' ', file_info)  # Normalize spaces/tabs
                
                # Validate and parse file_info
                parts = file_info.rsplit(' ', 1)  # Split into name and size
                if len(parts) != 2:
                    print(f"Invalid file info format: {file_info}")
                    continue
                
                file_name, size_str = parts
                try:
                    size_bytes = convert_to_bytes(size_str)
                except ValueError as e:
                    print(f"Error converting size: {e}")
                    continue
                
                # Check for new files
                if file_name not in [file[0] for file in file_lists]:
                    file_lists.append((file_name, size_bytes))
    except Exception as e:
        print(f"Failed to retrieve file list from server: {e}")
    return file_lists

def download_chunk(host, port, file_name, chunk_id, start, end, progress, lock, completion_flags):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        request = f"DOWNLOAD {file_name} {chunk_id} {start} {end}\n"
        reliable_send(s, (host, port), request.encode(), chunk_id)

        with open(f"{file_name}.part{chunk_id}", 'wb') as f:
            total_received = 0
            while total_received < (end - start + 1):
                data, _ = reliable_receive(s)
                if data is None:
                    break
                f.write(data)
                total_received += len(data)
                with lock:
                    progress[chunk_id] += len(data)

        # Mark this chunk as completed
        completion_flags[chunk_id] = True

def download_file(host, port, file_name, file_size):
    chunk_size_temp = file_size // 4  # Ensure all chunks are covered
    chunk_size = [chunk_size_temp, chunk_size_temp, chunk_size_temp, file_size - 3*chunk_size_temp]
    chunk_idx = 0
    progress = [0] * 4
    completion_flags = [False] * 4
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i in range(4):
            start = i * chunk_size[i]
            end = min(start + chunk_size[i] - 1, file_size - 1)
            futures.append(executor.submit(download_chunk, host, port, file_name, i, start, end, progress, lock, completion_flags))

        while not all(completion_flags):
            time.sleep(0.1)
            with lock:
                chunk_idx = (chunk_idx + 1) % 4
                progress_percentages = [min(p * 100 // chunk_size[chunk_idx], 100) for p in progress]
                progress_str = f"Progress: {progress_percentages}%"
                sys.stdout.write(f"\r{progress_str}")
                sys.stdout.flush()

    with open(f"{file_name}", 'wb') as f:
        for i in range(4):
            with open(f"{file_name}.part{i}", 'rb') as part:
                f.write(part.read())
            os.remove(f"{file_name}.part{i}")
    print(f"\nDownload completed: {file_name}")

def get_files_to_download(downloaded_files, file_name):
    files = []
    with open(file_name, 'r') as f:
        lines = f.readlines()
        start_reading = False
        for line in lines:
            if start_reading:
                if line.strip() == "":
                    break
                file_info = line.strip()
                file_name = file_info.split()[0]
                if file_name not in downloaded_files:
                    # Find the file size in the global file_lists
                    for file, size in file_lists:
                        if file == file_name:
                            files.append((file, size))
                            break
            if line.strip() == "Enter the files you want to download:":
                start_reading = True
    return files

def main():
    input_file = 'input.txt'
    host = input("Enter the server IP address: ")
    port = 9000
    downloaded_files = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            print("Connected to the UDP server successfully.")
            
            # # Send LIST request to server
            # reliable_send(s, (host, port), "LIST\n".encode(), 0)
            # response, _ = reliable_receive(s)
            # if response:
            #     print("Available files on server:")
            #     print(response.decode())

            try:
                while True:
                    new_files = read_new_files(s, host, port)
                    files_to_download = get_files_to_download(downloaded_files, input_file)

                    with open(input_file, 'w') as f:
                        for file, size in new_files:
                            f.write(f"{file} {size}\n")
                        f.write("---------------------------------------\n")
                        f.write("Enter the files you want to download:\n")
                        for file in files_to_download:
                            f.write(f"{file}\n")

                    for file_info, file_size in files_to_download:
                        print(f"Downloading {file_info}\n")
                        download_file(host, port, file_info, file_size)
                        downloaded_files.add(file_info)
                    time.sleep(5)
            except KeyboardInterrupt:
                reliable_send(s, (host, port), "QUIT\n".encode(), 0)
                print("\nClient stopped.")
    except Exception as e:
        print(f"Failed to connect to the server: {e}")

if __name__ == "__main__":
    main()