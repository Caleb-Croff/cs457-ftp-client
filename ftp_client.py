"""Command-line FTP client implemented using raw TCP sockets.

This client connects to an FTP server, issues commands, and transfers data
using active mode (PORT). It supports a subset of RFC959 commands suitable
for CS457 coursework.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple


Response = Tuple[int, List[str]]


@dataclass
class FTPResponse:
    code: int
    lines: List[str]

    def is_positive_completion(self) -> bool:
        return 200 <= self.code < 300

    def is_positive_preliminary(self) -> bool:
        return self.code in (125, 150)

    def is_error(self) -> bool:
        return self.code >= 400

    def __str__(self) -> str:
        return "\n".join(self.lines)


class FTPClient:
    def __init__(self) -> None:
        self.control_socket: Optional[socket.socket] = None
        self.control_file = None
        self.connected_host: Optional[str] = None
        self.last_type: Optional[str] = None

    # ------------------------------------------------------------------
    # Connection and command helpers
    # ------------------------------------------------------------------
    def connect(self, host: str, port: int = 21) -> FTPResponse:
        if self.control_socket is not None:
            raise RuntimeError("Already connected. Use close before opening a new connection.")

        addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        af, socktype, proto, _, sockaddr = addr_info[0]
        sock = socket.socket(af, socktype, proto)
        sock.connect(sockaddr)
        self.control_socket = sock
        self.control_file = sock.makefile("r", encoding="utf-8", newline="\r\n")
        self.connected_host = host
        response = self._read_response()
        print(response)
        return response

    def close(self) -> None:
        if self.control_file is not None:
            try:
                self.control_file.close()
            finally:
                self.control_file = None
        if self.control_socket is not None:
            try:
                self.control_socket.close()
            finally:
                self.control_socket = None
        self.connected_host = None
        self.last_type = None

    def _send_raw(self, data: str) -> None:
        if self.control_socket is None:
            raise RuntimeError("Not connected to any FTP server.")
        msg = f"{data}\r\n"
        self.control_socket.sendall(msg.encode("utf-8"))

    def send_command(self, command: str) -> FTPResponse:
        self._send_raw(command)
        response = self._read_response()
        print(response)
        return response

    def _read_response(self) -> FTPResponse:
        if self.control_file is None:
            raise RuntimeError("Control connection is not established.")

        lines: List[str] = []
        first_line = self.control_file.readline()
        if not first_line:
            raise ConnectionError("Connection closed by server.")
        first_line = first_line.rstrip("\r\n")
        lines.append(first_line)

        if len(first_line) < 3 or not first_line[:3].isdigit():
            raise ValueError(f"Invalid FTP response line: {first_line!r}")
        code = int(first_line[:3])

        if len(first_line) > 3 and first_line[3] == "-":
            # Multiline response: continue until line with same code and space
            while True:
                next_line = self.control_file.readline()
                if not next_line:
                    raise ConnectionError("Incomplete multiline response from server.")
                next_line = next_line.rstrip("\r\n")
                lines.append(next_line)
                if next_line.startswith(f"{code} "):
                    break
        return FTPResponse(code=code, lines=lines)

    # ------------------------------------------------------------------
    # Data connection helpers
    # ------------------------------------------------------------------
    def _prepare_data_connection(self) -> Tuple[socket.socket, Tuple[str, int]]:
        if self.control_socket is None:
            raise RuntimeError("Not connected to any FTP server.")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("", 0))
        listener.listen(1)

        local_ip, port = listener.getsockname()
        # Determine outward facing IP. Some servers need actual interface.
        if local_ip == "0.0.0.0":
            local_ip = self.control_socket.getsockname()[0]

        port_high = port // 256
        port_low = port % 256
        ip_parts = local_ip.split(".")
        port_command = f"PORT {','.join(ip_parts + [str(port_high), str(port_low)])}"
        response = self.send_command(port_command)
        if response.is_error():
            listener.close()
            raise RuntimeError(f"PORT command failed: {response}")
        return listener, (local_ip, port)

    def _ensure_type(self, mode: str) -> None:
        if self.last_type == mode:
            return
        response = self.send_command(f"TYPE {mode}")
        if response.is_error():
            raise RuntimeError(f"Failed to set transfer type {mode}: {response}")
        self.last_type = mode

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def handle_list(self, path: Optional[str] = None) -> None:
        self._ensure_type("A")
        listener, _ = self._prepare_data_connection()
        cmd = "LIST" if path is None else f"LIST {path}"
        prelim = self.send_command(cmd)
        if not prelim.is_positive_preliminary():
            listener.close()
            if prelim.is_error():
                raise RuntimeError(f"LIST failed: {prelim}")
            return

        data_socket, _ = listener.accept()
        listener.close()

        def receive_listing(sock: socket.socket) -> List[str]:
            buffer = []
            with sock:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer.append(chunk.decode("utf-8", errors="replace"))
            return buffer

        threads_result: List[str] = []

        def worker() -> None:
            threads_result.extend(receive_listing(data_socket))

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join()

        listing = "".join(threads_result)
        if listing:
            print(listing, end="" if listing.endswith("\n") else "\n")

        completion = self._read_response()
        print(completion)

    def handle_retr(self, remote_path: str, local_path: Optional[str] = None) -> None:
        self._ensure_type("I")
        listener, _ = self._prepare_data_connection()
        target_path = local_path or os.path.basename(remote_path)
        if not target_path:
            raise ValueError("Local filename could not be determined.")

        prelim = self.send_command(f"RETR {remote_path}")
        if not prelim.is_positive_preliminary():
            listener.close()
            if prelim.is_error():
                raise RuntimeError(f"RETR failed: {prelim}")
            return

        data_socket, _ = listener.accept()
        listener.close()

        def worker() -> None:
            with data_socket, open(target_path, "wb") as outfile:
                while True:
                    chunk = data_socket.recv(4096)
                    if not chunk:
                        break
                    outfile.write(chunk)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join()

        completion = self._read_response()
        print(completion)

    def handle_stor(self, local_path: str, remote_path: Optional[str] = None) -> None:
        self._ensure_type("I")
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        listener, _ = self._prepare_data_connection()
        target_path = remote_path or os.path.basename(local_path)
        if not target_path:
            raise ValueError("Remote filename could not be determined.")

        prelim = self.send_command(f"STOR {target_path}")
        if not prelim.is_positive_preliminary():
            listener.close()
            if prelim.is_error():
                raise RuntimeError(f"STOR failed: {prelim}")
            return

        data_socket, _ = listener.accept()
        listener.close()

        def worker() -> None:
            with data_socket, open(local_path, "rb") as infile:
                while True:
                    chunk = infile.read(4096)
                    if not chunk:
                        break
                    data_socket.sendall(chunk)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join()

        completion = self._read_response()
        print(completion)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def ensure_connected(self) -> None:
        if self.control_socket is None:
            raise RuntimeError("Not connected to any FTP server. Use 'open <host>' first.")

    def quit(self) -> None:
        if self.control_socket is None:
            return
        try:
            response = self.send_command("QUIT")
            if response.is_error():
                print("QUIT command reported an error; closing connection anyway.")
        finally:
            self.close()


def parse_command(line: str) -> Tuple[str, List[str]]:
    parts = line.strip().split()
    if not parts:
        return "", []
    cmd = parts[0].lower()
    args = parts[1:]
    return cmd, args


def repl() -> None:
    client = FTPClient()
    while True:
        try:
            line = input("ftp> ")
        except EOFError:
            print()
            client.quit()
            break

        cmd, args = parse_command(line)
        if not cmd:
            continue

        try:
            if cmd == "open":
                if not args:
                    print("Usage: open <host> [port]")
                    continue
                port = 21
                if len(args) >= 2:
                    try:
                        port = int(args[1])
                    except ValueError:
                        print("Invalid port number.")
                        continue
                client.connect(args[0], port)
            elif cmd == "user":
                client.ensure_connected()
                if len(args) != 1:
                    print("Usage: user <username>")
                    continue
                client.send_command(f"USER {args[0]}")
            elif cmd == "pass":
                client.ensure_connected()
                if len(args) != 1:
                    print("Usage: pass <password>")
                    continue
                client.send_command(f"PASS {args[0]}")
            elif cmd == "dir":
                client.ensure_connected()
                path = args[0] if args else None
                client.handle_list(path)
            elif cmd == "cd":
                client.ensure_connected()
                if len(args) != 1:
                    print("Usage: cd <path>")
                    continue
                client.send_command(f"CWD {args[0]}")
            elif cmd == "get":
                client.ensure_connected()
                if not args:
                    print("Usage: get <remote> [local]")
                    continue
                remote = args[0]
                local = args[1] if len(args) >= 2 else None
                client.handle_retr(remote, local)
            elif cmd == "put":
                client.ensure_connected()
                if not args:
                    print("Usage: put <local> [remote]")
                    continue
                local = args[0]
                remote = args[1] if len(args) >= 2 else None
                client.handle_stor(local, remote)
            elif cmd == "close":
                client.ensure_connected()
                client.quit()
            elif cmd == "quit":
                client.quit()
                break
            else:
                print(f"Unknown command: {cmd}")
        except Exception as exc:  # noqa: BLE001 - provide user feedback
            print(f"Error: {exc}")


def main() -> None:
    repl()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
