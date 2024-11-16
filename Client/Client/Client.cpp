// Client.cpp : Defines the entry point for the console application.
//
#include "stdafx.h"
#include "Client.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>
#include <tchar.h>
#include <vector>
#include <fstream>
#include <string>
#include <set>
#include <thread>
#include <chrono>
#include <regex>
#include <algorithm>
#include <sstream>
#include <conio.h>

#pragma comment(lib, "Ws2_32.lib")



vector<int> progress(4, 0); // Initialize progress for 4 chunks

using namespace std;

void download_chunk(const string& server_ip, unsigned int port, const string& file_name, int chunk_index, int chunk_size, int offset) {
	SOCKET ConnectSocket = INVALID_SOCKET;
	ConnectSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (ConnectSocket == INVALID_SOCKET) {
		_tprintf(_T("Error at socket(): %ld\n"), WSAGetLastError());
		return;
	}

	struct sockaddr_in clientService;
	clientService.sin_family = AF_INET;
	clientService.sin_port = htons(port);
	inet_pton(AF_INET, server_ip.c_str(), &clientService.sin_addr);

	int iResult = connect(ConnectSocket, (SOCKADDR*)&clientService, sizeof(clientService));
	if (iResult == SOCKET_ERROR) {
		closesocket(ConnectSocket);
		_tprintf(_T("Unable to connect to server!\n"));
		return;
	}

	string message = "START " + file_name + " " + to_string(chunk_index) + " " + to_string(chunk_size) + " " + to_string(offset);
	iResult = send(ConnectSocket, message.c_str(), message.length(), 0);
	if (iResult == SOCKET_ERROR) {
		closesocket(ConnectSocket);
		_tprintf(_T("Unable to send START message to download chunk!\n"));
		return;
	}

	// Send the file name and chunk information to the server
	int name_length = file_name.length();
	iResult = send(ConnectSocket, (char*)&name_length, sizeof(name_length), 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		return;
	}
	iResult = send(ConnectSocket, file_name.c_str(), name_length, 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		return;
	}

	// Send the chunk index, size, and offset
	iResult = send(ConnectSocket, (char*)&chunk_index, sizeof(chunk_index), 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		return;
	}
	iResult = send(ConnectSocket, (char*)&chunk_size, sizeof(chunk_size), 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		return;
	}
	iResult = send(ConnectSocket, (char*)&offset, sizeof(offset), 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		return;
	}

	// Receive the chunk data
	ofstream down(file_name + ".part" + to_string(chunk_index), ios::binary);
	char buffer[1024];
	int bytes_received = 0;
	while ((iResult = recv(ConnectSocket, buffer, sizeof(buffer), 0)) > 0) {
		down.write(buffer, iResult);
		bytes_received += iResult;
		progress[chunk_index] = (bytes_received * 100) / chunk_size;
		if (bytes_received >= chunk_size) break;
	}
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("recv failed: %d\n"), WSAGetLastError());
	}
	down.close();

	//Send END message
	message = "END " + to_string(chunk_index);
	iResult = send(ConnectSocket, message.c_str(), message.length(), 0);
	if (iResult == SOCKET_ERROR) {
		closesocket(ConnectSocket);
		_tprintf(_T("Unable to send END message!\n"));
		return;
	}
	closesocket(ConnectSocket);
}

void display_progress(string file_name) {
	while (true) {
		this_thread::sleep_for(chrono::seconds(1));
		system("cls");
		for (int i = 0; i < 4; i++) {
			cout << "Downloading " << file_name << " part " << i + 1 << "......" << progress[i] << "%" << endl;
		}
		if (all_of(progress.begin(), progress.end(), static_cast<bool(*)(int)>([](int p) -> bool { return p == 100; }))) {
			break;
		}
	}
}

void download_file(const string& server_ip, unsigned int port, const string& file_name, int file_size) {
	// Calculate chunk size
	int chunk_size = file_size / 4;

	// Create threads to download chunks
	vector<thread> threads;
	for (int i = 0; i < 4; ++i) {
		int offset = i * chunk_size;
		threads.emplace_back(download_chunk, server_ip, port, file_name, i, chunk_size, offset);
	}

	thread progress_thread(display_progress);

	// Wait for all threads to finish
	for (auto& t : threads) {
		t.join();
	}

	progress.thread.join();

	// Combine the chunks into the final file
	ofstream output(file_name, ios::binary);
	for (int i = 0; i < 4; ++i) {
		ifstream input(file_name + ".part" + to_string(i), ios::binary);
		output << input.rdbuf();
		input.close();
		remove((file_name + ".part" + to_string(i)).c_str());
	}
	output.close();
}

double byte_convert(string size) {
	regex pattern(R"(^([0-9]+(?:\.[0-9]+)?)\s*(KB|MB|GB)$)");
	smatch match;
	if (!regex_match(size, match, pattern)) {
		return 0;
	};

	double res = stod(match[1].str());
	int convert = 1;

	if (match[2] == "KB") {
		convert = 1000;
	}
	else if (match[2] == "MB") {
		convert = 1000000;
	}
	else if (match[2] == "GB") {
		convert = 1000000000;
	}
	return res * convert ;
}

int _tmain(int argc, TCHAR* argv[], TCHAR* envp[])
{
	int nRetCode = 0;

	//STEP 1: Initialize Winsock
	WSADATA wsaData;
	int iResult = WSAStartup(MAKEWORD(2, 2), &wsaData);
	if (iResult != 0) {
		_tprintf(_T("WSAStartup failed: %d\n"), iResult);
		return 1;
	}

	// Create a SOCKET for connecting to server
	SOCKET ConnectSocket = INVALID_SOCKET;
	/*
	Explain: 
	INVALID_SOCKET = (SOCKET)(~0)
	- SOCKET: This is a type definition used to represent a socket handle.
	- The bitwise NOT operator (~) is applied to 0, which flips all bits, resulting in a value where all bits are set to 1. 
	  For an unsigned integer, this is the maximum possible value 
	  (e.g., 0xFFFFFFFF for a 32-bit integer).
	*/

	ConnectSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	/*
	Explain: creates a TCP socket that uses the IPv4 address family.
	- socket() -> to create a socket, which is an endpoint for communication. 
	              It returns a socket descriptor, which is a handle used to 
				  reference the socket in subsequent operations.
	- AF_INET: This specifies the address family. 
			   AF_INET indicates that the socket will use the IPv4 protocol.
	- SOCK_STREAM: This specifies the socket type. 
				   SOCK_STREAM indicates that the socket will be a stream socket, 
				   which provides reliable, two-way, connection-based byte streams. 
				   This is typically used for **TCP** connections.
	- IPPROTO_TCP: This specifies the protocol to be used with the socket. 
				   IPPROTO_TCP indicates that the Transmission Control Protocol (TCP) will be used.
	*/

	if (ConnectSocket == INVALID_SOCKET) {
		_tprintf(_T("Error at socket(): %ld\n"), WSAGetLastError());
		WSACleanup();
		return 1;
	}

	//STEP 2: Specify server address
	char sAdd[1000];
	unsigned int port = 1234; // Same port as server
	/*
	A computer has 65,536 ports available for use, ranging from 0 to 65,535.
	1.	Well-Known Ports (0-1023)
	2.	Registered Ports (1024-49151)
	3.	Dynamic or Private Ports (49152-65535)
	While you can pick a port number randomly, it is important to ensure it does not 
	conflict with other services and follows best practices for port selection.
	*/
	cout << "Enter server IP address: ";
	cin.getline(sAdd, 1000);

	sockaddr_in clientService;
	clientService.sin_family = AF_INET;
	clientService.sin_port = htons(port);
	inet_pton(AF_INET, sAdd, &clientService.sin_addr);
	/*
	Explain: converts the server IP address from its text representation 
			 to its binary form and stores it in the sin_addr field of the clientService structure.
	- inet_prton(): convert an IP address from its text (string) form to its binary (numeric) form.
	-- AF_INET: This specifies the address family. 
				AF_INET indicates that the function should interpret the address as an IPv4 address.
	-- sAdd: This is a **pointer** to the null-terminated string 
			 containing the IP address in text form (e.g., "192.168.1.1").
	-- &clientService.sin_addr: This is a pointer to the destination 
								where the binary form of the IP address will be stored. 
								clientService.sin_addr is a field in the sockaddr_in structure 
								that holds the IP address in network byte order.
	*/

	//STEP 3: Connect to server
	iResult = connect(ConnectSocket, (SOCKADDR*)&clientService, sizeof(clientService));
	/*
	Explain: connect the client's socket (ConnectSocket) to the server's socket 
			 using the address and port specified in the clientService structure.
	- ConnectSocket: socket descriptor that identifies the socket.
	- name:  A pointer to a sockaddr structure that contains the address of the server to connect to
	- namelen: The length, in bytes, of the address structure pointed to by name.
	*/

	if (iResult == SOCKET_ERROR) {
		closesocket(ConnectSocket);
		ConnectSocket = INVALID_SOCKET;
		_tprintf(_T("Unable to connect to server!\n"));
		WSACleanup();
		return 1;
	}

	printf("\n Client connected to server");

	//STEP 4: Receive client ID from server
	int id;
	iResult = recv(ConnectSocket, (char*)&id, sizeof(id), 0);
	/*
	Explain: to receive the client ID from the server and store it in the id variable.
	   int recv(SOCKET s, char *buf, int len, int flags);
	- s: The socket descriptor from which to receive data.
	- buf: A pointer to the buffer where the received data will be stored.
	- len: The length, in bytes, of the buffer.
	- flags: Flags to modify the behavior of the function (usually set to 0 for default behavior).
	*/

	if (iResult > 0) {
		printf(" \nThis is client number %d\n", id + 1);
	}
	else {
		_tprintf(_T("recv failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		WSACleanup();
		return 1;
	}

	//MODIFY HER
	string exit_sign;
	vector<string> downloaded;
	while (true) {
		//This loop will realize the 5s-waiting to update both the list of available files to download,
		//and new files that the users want to download
		// Request the list of files from the server
		vector<pair<string, string>> list_files;
		char buffer[1024];
		string file_list;
		iResult = send(ConnectSocket, "LIST", 4, 0); // Send a request to get the list of files
		while ((iResult = recv(ConnectSocket, buffer, sizeof(buffer) - 1, 0)) > 0) {
			buffer[iResult] = '\0'; //nullterminate each time we take in the data
			file_list += buffer;
		}

		//Split the file_list into individual files name
		int pos;
		string delimiter = "\n";
		while ((pos = file_list.find(delimiter)) != string::npos) {
			string token = file_list.substr(0, pos); //token = "filename.txt 50MB"

			stringstream ss(token);
			string name;
			getline(ss, name, ' ');
			string size;
			getline(ss, size);
			list_files.push_back({name, size});
			file_list.erase(0, pos + delimiter.length());
		}

		//Print out the list of filenames into input.txt
		ofstream fp("input.txt");
		if (!fp) {
			cerr << "Cannot accessed input.txt\n";
			return 1;
		}
		for (const auto i : list_files) {
			fp << i.first << " " << i.second << endl;
		}
		fp << "--------------------------------------------------\n";
		fp << "Enter the files that you want to download: \n";
		fp << "NOTE: You have to enter the exact file names\n";
		fp << "--------------------------------------------------\n";
		fp.close();

		vector<string> new_download;
		ifstream file("input.txt");
		if (!file) {
			cerr << "Cannot accessed input.txt\n";
			return 1;
		}
		string line;
		// Move the cursor to the "NOTE:..." line
		while (getline(file, line)) {
			if (line.find("NOTE:") != string::npos) {
				break; // Exit the loop once the "NOTE:" line is found
			}
		}
		getline(file, line); //Move to the -------------------- line
		while (getline(file, line)) {
			regex pattern(R"((\S+\.\S+))");
			smatch match;
			if (line.empty()) {
				break;
			}
			if (regex_match(line, match, pattern)) {
				new_download.push_back(match[1].str());
			}
			else {
				cout << "You have entered an invalid file name. Please check again.\n";
				break;
			}
		}
		//Check if the files have already been downloaded
		for (const auto& file : new_download) {
			// Check if the file is already downloaded
			auto it = find(downloaded.begin(), downloaded.end(), file);
			if (it != downloaded.end()) {
				continue;
			}
			else {
				// If this is a new file, we will download it
				downloaded.push_back(file);

				// Search for the file in list_files to seek for the file size
				auto file_it = find_if(list_files.begin(), list_files.end(), [&file](const pair<string, string>& p) {
					return p.first == file;
					});

				if (file_it != list_files.end()) {
					download_file(sAdd, 1234, file, byte_convert(file_it->second));
				}
				else {
					cerr << "File " << file << " not found in the list_files.\n";
				}
			}
		}


		if (_kbhit()) { // Check if a key has been pressed
			getline(cin, exit_sign);
			if (exit_sign == "exit") {
				break;
			}
		}
		// Wait for 5 seconds before checking the input.txt file again
		this_thread::sleep_for(chrono::seconds(5));
	}

	




	//END PREPARATION
	
	//SEND THE REQUEST TO THE SERVER
	
	//STEP 5: Send first number to server
	/*printf("Sending first number, value %d to server\n", numbers[0]);
	iResult = send(ConnectSocket, (char*)&numbers[0], sizeof(int), 0);*/
	/*
	Explain: 
	- (char*)&numbers[0]: casts the address of the first element of the numbers array to a char* pointer. 
						  data to be sent is the first random number.
	- sizeof(int): size of the data to be sent
	*/
	/*if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		WSACleanup();
		return 1;
	}*/
	
	//STEP 6: Send second number to server
	/*printf("Sending second number, value %d to server\n", numbers[1]);
	iResult = send(ConnectSocket, (char*)&numbers[1], sizeof(int), 0);
	if (iResult == SOCKET_ERROR) {
		_tprintf(_T("send failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		WSACleanup();
		return 1;
	}*/
	
	//END SENDING REQUEST
	
	//STEP 7: Receive result from server
	int count;
	iResult = recv(ConnectSocket, (char*)&count, sizeof(count), 0);
	if (iResult > 0) {
		printf("Total number of prime numbers sent by ALL clients: %d \n", count);
	}
	else {
		_tprintf(_T("recv failed: %d\n"), WSAGetLastError());
		closesocket(ConnectSocket);
		WSACleanup();
		return 1;
	}

	// Cleanup
	closesocket(ConnectSocket);
	WSACleanup();

	getchar();
	return nRetCode;
}
