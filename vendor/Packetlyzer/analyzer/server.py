"""Socket server module for receiving newline-delimited JSON from the addon."""

import json
import logging
import queue
import socket
import threading

logger = logging.getLogger(__name__)


class PacketServer:
    """TCP server accepting one addon connection at a time.

    Runs on a daemon thread. Reads newline-delimited JSON, parses each line,
    and places parsed dicts onto a thread-safe queue. Malformed lines are
    logged and skipped.
    """

    def __init__(self, host: str, port: int, packet_queue: queue.Queue):
        """Initialize the server.

        Args:
            host: Address to bind to (e.g. '127.0.0.1').
            port: Port number to listen on.
            packet_queue: Thread-safe queue for parsed JSON messages.
        """
        self._host = host
        self._port = port
        self._queue = packet_queue
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """Whether the server is currently running."""
        return self._running

    def start(self) -> None:
        """Start listening on a background daemon thread.

        Must be called before pygame init to ensure the server is ready
        to accept connections immediately.
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(1)
        self._running = True

        self._thread = threading.Thread(target=self._server_loop, daemon=True)
        self._thread.start()
        logger.info("PacketServer listening on %s:%d", self._host, self._port)

    def stop(self) -> None:
        """Shutdown server and close connections."""
        self._running = False

        # Close the client socket if connected
        if self._client_socket:
            try:
                self._client_socket.close()
            except OSError:
                pass
            self._client_socket = None

        # Close the server socket to unblock accept()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        # Wait for the thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("PacketServer stopped")

    def _server_loop(self) -> None:
        """Main server loop: accept connections and read data."""
        while self._running:
            try:
                self._server_socket.settimeout(1.0)
                try:
                    client, addr = self._server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    # Socket was closed (stop() called)
                    break

                self._client_socket = client
                logger.info("Addon connected from %s:%d", addr[0], addr[1])
                self._handle_client(client)

            except OSError:
                # Server socket closed during shutdown
                break

    def _handle_client(self, client: socket.socket) -> None:
        """Read newline-delimited JSON from a connected client.

        Buffers incoming data, splits on newlines, parses each complete
        line as JSON and places it on the queue. Malformed lines are
        logged and skipped.
        """
        buffer = ""
        try:
            while self._running:
                client.settimeout(1.0)
                try:
                    data = client.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break

                if not data:
                    # Client disconnected
                    break

                buffer += data.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        self._queue.put(parsed)
                    except json.JSONDecodeError:
                        logger.warning("Malformed JSON line: %s", line)

        except Exception as e:
            logger.error("Error handling client: %s", e)
        finally:
            try:
                client.close()
            except OSError:
                pass
            self._client_socket = None
            logger.info("Addon disconnected, resuming listening")


def validate_port(port_str: str) -> int:
    """Validate a port string from CLI arguments.

    Args:
        port_str: The string value of the --port argument.

    Returns:
        The validated port as an integer.

    Raises:
        SystemExit: If the port is not a valid integer in range 1024-65535.
    """
    import sys

    try:
        port = int(port_str)
    except (ValueError, TypeError):
        print(
            f"Error: --port must be an integer in the range 1024-65535, got: {port_str!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    if port < 1024 or port > 65535:
        print(
            f"Error: --port must be in the range 1024-65535, got: {port}",
            file=sys.stderr,
        )
        sys.exit(1)

    return port
