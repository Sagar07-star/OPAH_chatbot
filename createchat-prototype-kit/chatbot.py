
import os
import json
import urllib.request
import urllib.error

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SERVER_URL = "http://127.0.0.1:8765"
MOCK_USER_ID = os.getenv("MOCK_USER_ID", "clt_001")

SYSTEM_PROMPT = """
You are CREATEchat, the AI assistant for OPAH photo and video production clients.

Help clients manage projects, find creative professionals, understand packages,
check deliverables, and communicate with their creative team.

You have access to business tools. Use them whenever relevant.

IMPORTANT RULES:
1. Never invent client, project, booking, or pricing information.
2. Retrieve information using tools before answering questions about client data.
3. Never claim an action succeeded unless the backend confirms it.
4. Creating or updating projects and other staged actions require client approval.
5. Never approve a proposal yourself.
6. Checkout, cancellation, messages and reviews are handoffs, not completed actions.
7. Explain errors honestly.
8. Never reveal another client's private information.
9. Ask the client for missing information when necessary.
10. Be friendly, clear and concise.
"""


def server_request(path, method="GET", payload=None):
    url = SERVER_URL + path

    headers = {
        "X-Mock-User": MOCK_USER_ID,
        "Content-Type": "application/json"
    }

    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        return json.loads(error.read().decode("utf-8"))

    except urllib.error.URLError as error:
        return {"error": "server_unavailable", "message": str(error)}


def load_tools():
    schemas = server_request("/tools")

    if not isinstance(schemas, list):
        raise RuntimeError(f"Could not load backend tools: {schemas}")

    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"]
        }
        for tool in schemas
    ]


def execute_tool(name, arguments):
    print(f"\n[CREATEchat is using: {name}]")

    return server_request(
        f"/tools/{name}",
        method="POST",
        payload=arguments
    )


def chat_with_ai(message, history, tools):
    history.append({
        "role": "user",
        "content": message
    })

    for _ in range(8):
        response = client.responses.create(
            model="gpt-5-mini",
            instructions=SYSTEM_PROMPT,
            input=history,
            tools=tools,
            tool_choice="auto"
        )

        history.extend([
            item.model_dump(exclude_none=True)
            for item in response.output
        ])

        function_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not function_calls:
            return response.output_text

        for call in function_calls:
            try:
                arguments = json.loads(call.arguments)

                result = execute_tool(
                    call.name,
                    arguments
                )

            except Exception as error:
                result = {
                    "error": "tool_execution_error",
                    "message": str(error)
                }

            history.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result)
            })

    return "I couldn't complete that request. Please try again."


def main():
    print("Connecting to CREATEchat backend...")

    health = server_request("/health")

    if health.get("status") != "ok":
        print("Backend is unavailable:", health)
        return

    tools = load_tools()

    print("Backend connected!")
    print(f"Signed in as demo client: {MOCK_USER_ID}")
    print(f"Loaded {len(tools)} business tools.")

    print("\nCREATEchat AI is ready!")
    print("Type 'exit' to quit.")
    print("To approve a staged proposal, type APPROVE followed by its ID.")
    print("To reject a staged proposal, type REJECT followed by its ID.")

    history = []

    while True:
        message = input("\nYou: ").strip()

        if message.lower() == "exit":
            print("CREATEchat: Goodbye!")
            break

        if not message:
            continue

        # Explicit client approval; never exposed as an AI tool.
        parts = message.split()

        if len(parts) == 2 and parts[0].upper() in ("APPROVE", "REJECT"):
            action = parts[0].lower()
            proposal_id = parts[1]

            result = server_request(
                f"/proposals/{proposal_id}/{action}",
                method="POST",
                payload={}
            )

            print("\nCREATEchat:", json.dumps(result, indent=2))
            continue

        try:
            reply = chat_with_ai(message, history, tools)
            print("\nCREATEchat:", reply)

        except Exception as error:
            print("\nError:", error)


if __name__ == "__main__":
    main()
