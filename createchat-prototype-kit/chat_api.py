
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chatbot import (
    server_request,
    load_tools,
    chat_with_ai,
)

HOST = "127.0.0.1"
PORT = 8766

sessions = {}
tools = load_tools()


class ChatHandler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

        self.wfile.write(response)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        if self.path != "/chat":
            return self.send_json(404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            message = body.get("message", "").strip()
            conversation_id = body.get("conversation_id", "default")

            if not message:
                return self.send_json(
                    400,
                    {"error": "Message cannot be empty"}
                )

            if len(message) > 5000:
                return self.send_json(
                    400,
                    {"error": "Message is too long"}
                )

            if conversation_id not in sessions:
                sessions[conversation_id] = []

            history = sessions[conversation_id]

            reply = chat_with_ai(message, history, tools)

            return self.send_json(200, {
                "type": "message",
                "message": reply,
                "conversation_id": conversation_id
            })

        except Exception as error:
            print("Chat API error:", error)

            return self.send_json(500, {
                "error": "chat_error",
                "message": "Something went wrong. Please try again."
            })

    def log_message(self, format, *args):
        print("Chat API:", format % args)


if __name__ == "__main__":
    health = server_request("/health")

    if health.get("status") != "ok":
        raise RuntimeError("The OPAH mock backend is not running.")

    print("CREATEchat AI API is ready!")
    print(f"Loaded {len(tools)} business tools.")
    print(f"Listening at http://{HOST}:{PORT}")

    server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
    server.serve_forever()
