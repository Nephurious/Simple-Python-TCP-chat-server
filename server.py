import socket
from typing import Deque
from threading import Thread, Lock, Event
import argparse

class ChatServer:
    def __init__(self, ip="127.0.0.1", port=8888):
        socket.setdefaulttimeout(10)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((ip, port))
        print("Initialised server at {} port {}".format(ip, port))
        self.sock.listen(5)
        self.message_queue = Deque()
        self.connections = set()
        self.locks = {"msg queue": Lock(), "connections": Lock()}
        self.msg_event = Event()
        self.stopped = False

    def listen(self):
        print("Server now listening for connections.")
        try:
            while True:
                try:
                    client, address = self.sock.accept()
                except socket.timeout:
                    continue
                if (client, address) in self.connections:
                    print("Client {} {} already connected.".format(client, address))
                    client.close()
                    continue
                Thread(target=self.client_listener, args=(client, address)).start()
        except KeyboardInterrupt:
            print("Server shutting down")
            self.stopped = True
            self.msg_event.set()
            with self.locks["connections"]:
                for client, address in self.connections:
                    client.sendall(bytes("\nServer shutting down.\n", "utf-8"))
                    client.close()
            return

    def client_listener(self, client, address):
        print("Connected with {}".format(address))
        client.sendall(bytes("Enter your username: ", "utf-8"))
        client.settimeout(30)
        try:
            username = client.recv(1024).decode("utf-8").strip()
        except socket.timeout:
            print("Client {} timed out".format(address))
            client.sendall(bytes("Disconnected due to timeout", "utf-8"))
            client.close()
            return
        if not username:
            return
        client.settimeout(900)
        client.sendall(bytes("Welcome, {}.\nType 'logout' to logout\n\n".format(username), "utf-8"))
        with self.locks["msg queue"]:
            self.message_queue.append(((client, address), "[Server]", "{} connected".format(username)))
            self.msg_event.set()
        with self.locks["connections"]:
            self.connections.add((client, address))
        while True:
            if self.stopped:
                return
            try:
                # Does not buffer inputs. Long messages will be split.
                msg = client.recv(1024)
            except socket.timeout:
                print("Client {} timed out".format(address))
                client.sendall(bytes("Disconnected due to timeout", "utf-8"))
                client.close()
                return
            except Exception:
                return
            if msg:
                msg_decoded = msg.decode("utf-8").strip()
                if msg_decoded == "logout":
                    self.__logout(client, address, username)
                    return
                print("{}: {}".format(username, msg_decoded))
                with self.locks["msg queue"]:
                    self.message_queue.append(((client, address), username, msg_decoded))
                    self.msg_event.set()
            else:
                self.__logout(client, address, username)
                return

    def __logout(self, client, address, username):
        print("Client {} disconnected.".format(address))
        with self.locks["msg queue"]:
            self.message_queue.append(((client, address), "[Server]", "{} disconnected".format(username)))
            self.msg_event.set()
        with self.locks["connections"]:
            self.connections.remove((client, address))
        client.close()
        return

    def messege_sender(self):
        while True:
            if self.stopped:
                return
            self.msg_event.wait(10)
            with self.locks["msg queue"]:
                while len(self.message_queue) > 0:
                    client_addr, username, message = self.message_queue.popleft()
                    output_message = "{}: {}\n".format(username, message)
                    with self.locks["connections"]:
                        for client, address in self.connections:
                            if (client, address) != client_addr:
                                client.sendall(bytes(output_message, "utf-8"))
                self.msg_event.clear()
    
    def start_server(self):
        msg_t = Thread(target=self.messege_sender).start()
        self.listen()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A simple TCP chat server")
    parser.add_argument('ip', nargs='?', default='127.0.0.1', type=str, help="ip to host the server")
    parser.add_argument('port', nargs='?', default=8888, type=int, help="port")
    args = parser.parse_args()
    server = ChatServer(args.ip, args.port)
    server.start_server()