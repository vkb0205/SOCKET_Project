// Server.cpp : Defines the entry point for the console application.
//
#include <winsock2.h>
#include <ws2tcpip.h>
#include <math.h>
#include <iostream>
#include <vector>
#include <thread>
#include <fstream>
#include <sstream>
#pragma comment(lib, "Ws2_32.lib") 
#define INPUT "input.txt"

#ifdef _DEBUG
#define new DEBUG_NEW
#endif

using namespace std;

string int_to_str(int n) {
	stringstream ss;
	ss << n;
	return ss.str();
}

thread handleClient(SOCKET clientSocket, int clientID) {
	cout << "Client " << clientID << " connected. \n";
	//Convert clientID to string
	string clientIDStr = int_to_str(clientID);
	//Send the client ID to the client
	int iSendResult = send(clientSocket, clientIDStr.c_str(), clientIDStr.size(), 0);
	if (iSendResult == SOCKET_ERROR) {
		cout << "send clientID failed: " << WSAGetLastError() << endl;
		closesocket(clientSocket);
		WSACleanup();
		return thread();
	}
	char recvbuf[1024];
	int recvbuflen = 1024;
	int iResult;

	do {
		iResult = recv(clientSocket, recvbuf, recvbuflen, 0);
		if (iResult > 0) {
			recvbuf[iResult] = '\0';
			string request(recvbuf);
			cout << request << endl;

			if (request == "LIST") {
				ifstream fp(INPUT);
				if (!fp) {
					cout << "Cannot open input.txt\n";
					continue;
				}
				string buffer;
				string files;
				while (getline(fp, buffer)) {
					files += buffer + "\n";
				}
				iResult = send(clientSocket, files.c_str(), files.size(), 0);
				if (iResult == SOCKET_ERROR) {
					cout << "send failed: " << WSAGetLastError() << endl;
					closesocket(clientSocket);
					WSACleanup();
					return thread();
				}
			}
			else if (request.find("START DOWNLOADING") != string::npos) {
				stringstream ss(request);
				//START DOWNLOADING filename.txt [chunk_index] [chunk_size]
				string bff;
				getline(ss, bff, ' ');
				getline(ss, bff, ' ');
				string filename;
				getline(ss, filename, ' ');
				int chunkIndex, chunkSize;
				ss >> chunkIndex >> chunkSize;
				ifstream file(filename, ios::binary);
				if (!file) {
					string errorMsg = "ERROR: File not found\n";
					send(clientSocket, errorMsg.c_str(), errorMsg.size(), 0);
					continue;
				}
				// Calculate the position to start reading the chunk
				file.seekg(chunkIndex * chunkSize, ios_base::beg);
				vector<char> buffer(chunkSize);
				file.read(buffer.data(), chunkSize);

				// Send the chunk to the client
				int bytesRead = file.gcount();
				int iSendResult = send(clientSocket, buffer.data(), bytesRead, 0);
				if (iSendResult == SOCKET_ERROR) {
					cout << "send failed: " << WSAGetLastError() << endl;
					closesocket(clientSocket);
					WSACleanup();
					return thread();
				}
			}
		}
		else if (iResult < 0) {
			cout << "recv failed: " << WSAGetLastError() << endl;
			closesocket(clientSocket);
			WSACleanup();
			return thread();
		}
		else {
			cout << "Connection closing..." << endl;
		}
	} while (iResult > 0);
	return thread();
}


int main(int argc, TCHAR* argv[], TCHAR* envp[])
{
	WSADATA wsaData;
	int iResult = WSAStartup(MAKEWORD(2, 2), &wsaData);
	if (iResult != 0) {
		cout << "WSAStartup failed: " << iResult << endl;
		return 1;
	}

	SOCKET server = INVALID_SOCKET;
	server = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (server == INVALID_SOCKET) {
		cout << "Error at socket(): " << WSAGetLastError() << endl;
		WSACleanup();
		return 1;
	}

	//Prepare the port to connect to this program/service
	sockaddr_in service;
	service.sin_family = AF_INET;
	service.sin_addr.s_addr = INADDR_ANY;
	service.sin_port = htons(1234);

	//Bind 
	if (bind(server, (SOCKADDR*)&service, sizeof(service)) == SOCKET_ERROR) {
		cout << "bind() failed\n";
		closesocket(server);
		WSACleanup();
		return 1;
	}

	//listen
	if (listen(server, SOMAXCONN) == SOCKET_ERROR) {
		cout << "listen() failed\n";
		closesocket(server);
		WSACleanup();
		return 1;
	}

	//Accept clients and handle each of them
	vector<thread> clientThreads;
	int clientID = 0;

	while (true) {
		sockaddr_in clientAddr;
		int clientAddrSize = sizeof(clientAddr);
		//accept client connections
		SOCKET clientSocket = INVALID_SOCKET;
		clientSocket = accept(server, (SOCKADDR*)&clientAddr, &clientAddrSize);
		if (clientSocket == INVALID_SOCKET) {
			cout << "accept() failed: " << WSAGetLastError() << endl;
			closesocket(server);
			WSACleanup();
			return 1;
		}
		clientThreads.push_back(thread(handleClient, clientSocket, ++clientID));
	}

	for (auto& t : clientThreads) {
		if (t.joinable()) {
			t.join();
		}
	}

	closesocket(server);
	WSACleanup();

	return 0;
}
