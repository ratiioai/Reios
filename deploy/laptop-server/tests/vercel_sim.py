"""
Local stand-ins for the Vercel setup:
  python vercel_sim.py site <dir> <port>          static site with SPA fallback (like Vercel's rewrite)
  python vercel_sim.py relay <port> <target_port>  TCP relay to nginx = "the laptop's old address"
"""
import http.server
import os
import socket
import socketserver
import sys
import threading


def site(directory, port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def end_headers(self):
            if self.path.startswith("/backend.json"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_head(self):
            path = self.translate_path(self.path)
            if not os.path.exists(path):
                self.path = "/index.html"
            return super().send_head()

        def log_message(self, *a):
            pass

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), H) as s:
        s.serve_forever()


def relay(port, target):
    def pipe(a, b):
        try:
            while (data := a.recv(65536)):
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.close()
                except OSError:
                    pass

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(256)
    while True:
        c, _ = srv.accept()
        u = socket.create_connection(("127.0.0.1", target))
        threading.Thread(target=pipe, args=(c, u), daemon=True).start()
        threading.Thread(target=pipe, args=(u, c), daemon=True).start()


if __name__ == "__main__":
    if sys.argv[1] == "site":
        site(sys.argv[2], int(sys.argv[3]))
    else:
        relay(int(sys.argv[2]), int(sys.argv[3]))
