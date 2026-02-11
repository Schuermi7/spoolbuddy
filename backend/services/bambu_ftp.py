"""
Bambu Lab Printer FTP Client

Provides FTPS access to Bambu Lab printers for downloading files.
Uses implicit FTPS on port 990 with SSL session reuse.
"""

import asyncio
import logging
import socket
import ssl
from ftplib import FTP, FTP_TLS  # nosec B402
from io import BytesIO

logger = logging.getLogger(__name__)


class ImplicitFTP_TLS(FTP_TLS):
    """FTP_TLS subclass for implicit FTPS (port 990) with session reuse."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def connect(self, host="", port=990, timeout=-999, source_address=None):
        """Connect to host, wrapping socket in TLS immediately (implicit FTPS)."""
        if host:
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if source_address:
            self.source_address = source_address

        # Create and wrap socket immediately (implicit TLS)
        self.sock = socket.create_connection((self.host, self.port), self.timeout, source_address=self.source_address)
        self.sock = self.ssl_context.wrap_socket(self.sock, server_hostname=self.host)
        self.af = self.sock.family
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        """Override to reuse SSL session for data connection (required by vsFTPd)."""
        conn, size = FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            # Reuse the SSL session from the control connection
            conn = self.ssl_context.wrap_socket(
                conn,
                server_hostname=self.host,
                session=self.sock.session,  # Reuse session!
            )
        return conn, size


class BambuFTPClient:
    """FTP client for retrieving files from Bambu Lab printers."""

    FTP_PORT = 990

    def __init__(self, ip_address: str, access_code: str):
        self.ip_address = ip_address
        self.access_code = access_code
        self._ftp: ImplicitFTP_TLS | None = None

    def connect(self) -> bool:
        """Connect to the printer FTP server (implicit FTPS on port 990)."""
        try:
            logger.debug(f"FTP connecting to {self.ip_address}:{self.FTP_PORT}")
            self._ftp = ImplicitFTP_TLS()
            self._ftp.connect(self.ip_address, self.FTP_PORT, timeout=10)
            logger.debug("FTP connected, logging in as bblp")
            self._ftp.login("bblp", self.access_code)
            logger.debug("FTP logged in, setting prot_p and passive mode")
            self._ftp.prot_p()
            self._ftp.set_pasv(True)
            logger.info(f"FTP connected successfully to {self.ip_address}")
            return True
        except Exception as e:
            logger.warning(f"FTP connection failed to {self.ip_address}: {e}")
            self._ftp = None
            return False

    def disconnect(self):
        """Disconnect from the FTP server."""
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                pass
            self._ftp = None

    def download_file(self, remote_path: str) -> bytes | None:
        """Download a file from the printer."""
        if not self._ftp:
            return None

        try:
            buffer = BytesIO()
            self._ftp.retrbinary(f"RETR {remote_path}", buffer.write)
            return buffer.getvalue()
        except Exception as e:
            logger.info(f"FTP download failed for {remote_path}: {e}")
            return None

    def download_file_try_paths(self, paths: list[str]) -> bytes | None:
        """Try downloading a file from multiple paths, return first success."""
        for path in paths:
            data = self.download_file(path)
            if data:
                return data
        return None


async def download_file_bytes_async(
    ip_address: str,
    access_code: str,
    remote_path: str,
    timeout: float = 30.0,
) -> bytes | None:
    """Async wrapper for downloading file as bytes."""
    loop = asyncio.get_event_loop()

    def _download():
        client = BambuFTPClient(ip_address, access_code)
        if client.connect():
            try:
                return client.download_file(remote_path)
            finally:
                client.disconnect()
        return None

    try:
        return await asyncio.wait_for(loop.run_in_executor(None, _download), timeout=timeout)
    except TimeoutError:
        logger.warning(f"FTP download timed out after {timeout}s for {remote_path}")
        return None


async def download_file_try_paths_async(
    ip_address: str,
    access_code: str,
    remote_paths: list[str],
    timeout: float = 30.0,
) -> bytes | None:
    """Try downloading a file from multiple paths using a single connection."""
    loop = asyncio.get_event_loop()

    def _download():
        client = BambuFTPClient(ip_address, access_code)
        if not client.connect():
            return None

        try:
            return client.download_file_try_paths(remote_paths)
        finally:
            client.disconnect()

    try:
        return await asyncio.wait_for(loop.run_in_executor(None, _download), timeout=timeout)
    except TimeoutError:
        logger.warning(f"FTP download timed out after {timeout}s")
        return None
