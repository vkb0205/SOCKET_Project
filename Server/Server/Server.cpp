// Server.cpp : Defines the entry point for the console application.
//

#include "stdafx.h"
#include "Server.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <math.h>
#include <iostream>


#ifdef _DEBUG
#define new DEBUG_NEW
#endif

using namespace std;


int _tmain(int argc, TCHAR* argv[], TCHAR* envp[])
{
	int nRetCode = 0;

	WSADATA wsaData;
	int iResult = WSAStartup(MAKEWORD(2, 2), &wsaData);
	/*
	Explain: initialize the Winsock library and prepare it for network operations. 
	- The first parameter is the version of Winsock that the application wants to use (in this case, MAKEWORD(2, 2) specifies version 2.2)
	- The second parameter is a pointer to a WSADATA structure that receives details about the Winsock implementation.
	*/
	if (iResult == SOCKET_ERROR) {
		cout << "WSAStartup Failed!\n";
		return 1;
	}

	SOCKET server = INVALID_SOCKET;
	server = socket(AF_INET, SOCK_STREAM, IPPROTO_IDP);
	if (server == INVALID_SOCKET) {
		cout << "Error at socket(): " << WSAGetLastError() << endl;
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


	return nRetCode;
}
