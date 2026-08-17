import os
import asyncio
from threading import Thread

try:
    import ngrok
except Exception:
    ngrok = None

from flask import Flask, request, Response

# Try to import AgentMail-related packages; provide local fallbacks so this
# example can run even if the real packages aren't installed.
try:
    from agentmail import AgentMail
    from agentmail_toolkit.openai import AgentMailToolkit
    from agents import Agent, Runner
except Exception:
    print("agentmail packages not available; using local stubs for development.")

    class AgentMail:
        class _Messages:
            @staticmethod
            def reply(inbox_id=None, message_id=None, text=None):
                print(f"[mock reply] inbox={inbox_id} message_id={message_id} text={text}")

        class _Inboxes:
            messages = _Messages()

        def __init__(self):
            self.inboxes = self._Inboxes()

    class AgentMailToolkit:
        def __init__(self, client):
            self.client = client

        def get_tools(self):
            return []

    class Agent:
        def __init__(self, name=None, instructions=None, tools=None):
            self.name = name
            self.instructions = instructions
            self.tools = tools or []

    class Runner:
        @staticmethod
        async def run(agent, prompt):
            class _Resp:
                def __init__(self, out):
                    self.final_output = out

            # Simple mock behavior: echo a short reply
            return _Resp(out=("Mock reply from Agent '" + (agent.name or "unknown") + "':\n" + (prompt[:500] if prompt else "")))


port = 8080
domain = os.getenv("WEBHOOK_DOMAIN")
inbox = f"{os.getenv('INBOX_USERNAME')}@agentmail.to"

if ngrok is not None and hasattr(ngrok, "forward"):
    try:
        listener = ngrok.forward(port, domain=domain, authtoken_from_env=True)
    except Exception as e:
        print(f"Failed to create ngrok tunnel: {e}")
        listener = None
else:
    print("ngrok not available; skipping tunnel creation.")
    listener = None
app = Flask(__name__)

client = AgentMail()

instructions = f"""
You are an email agent. Your name is AgentMail. Your email address is {inbox}.
Respond as if you are writing an email. Do not include the subject, only the body.
"""

agent = Agent(
    name="Email Agent",
    instructions=instructions,
    tools=AgentMailToolkit(client).get_tools(),
)

@app.route("/webhooks", methods=["POST"])
def receive_webhook():
    Thread(target=process_webhook, args=(request.json,)).start()
    return Response(status=200)


def process_webhook(payload):
    email = payload["message"]

    prompt = f"""
From: {email["from"]}
Subject: {email["subject"]}
Body:\n{email["text"]}
"""
    print("Prompt:\n\n", prompt, "\n")

    response = asyncio.run(Runner.run(agent, prompt))
    print("Response:\n\n", response.final_output, "\n")

    client.inboxes.messages.reply(inbox_id=inbox, message_id=email["message_id"], text=response.final_output)


if __name__ == "__main__":
    print(f"Inbox: {inbox}\n")

    app.run(port=port)
    
    
