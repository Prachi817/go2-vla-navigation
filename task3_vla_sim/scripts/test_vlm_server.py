"""Send one fake request to a running NaVILA VLM server -- no Isaac Sim needed.

Uses the same wire protocol as NaVILA-Bench's navila_eval.py: 8-byte big-endian
length prefix, then JSON {"images": [8 base64 JPEGs], "query": instruction}.
The images are blank grey, so the answer itself is meaningless; this only
checks that the server loads, answers, and answers in the expected format
("The next action is ...").

    $PY test_vlm_server.py            # navila env python, server on :54321

Do NOT "ping" the server with an empty connection (e.g. bash /dev/tcp or nc):
vlm_server.py reads a zero-length request, json.loads('') raises, and the
exception is not caught -- the server process exits.
"""
import base64
import io
import json
import socket

from PIL import Image

HOST, PORT = "localhost", 54321

img = Image.new("RGB", (640, 480), (128, 128, 128))
buf = io.BytesIO()
img.save(buf, format="JPEG")
b64 = base64.b64encode(buf.getvalue()).decode()

req = json.dumps({"images": [b64] * 8, "query": "Walk forward and stop at the door."}).encode()
s = socket.create_connection((HOST, PORT))
s.sendall(len(req).to_bytes(8, "big"))
s.sendall(req)

size = int.from_bytes(s.recv(8), "big")
data = b""
while len(data) < size:
    data += s.recv(4096)
print("NaVILA says:", json.loads(data.decode()))
