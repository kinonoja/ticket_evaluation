import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TICKETS_FILE = Path("tickets.json")
GEMINI_MODEL = "gemini-2.5-flash"


def get_ai_suggestions(description):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set the GEMINI_API_KEY environment variable to enable AI suggestions.")

    prompt = (
        "Suggest practical ways to fix or investigate this reported campus problem. "
        "Give concise, numbered steps.\n\n"
        f"Ticket description:\n{description}"
    )
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}],
            }
        ]
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        try:
            error_result = json.loads(error.read().decode("utf-8"))
            error_message = error_result.get("error", {}).get("message")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            error_message = None
        message = f"AI request failed with HTTP {error.code}"
        if isinstance(error_message, str) and error_message:
            message += f": {error_message}"
        raise RuntimeError(message) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Could not reach the AI service. Check your internet connection and try again.") from None
    except json.JSONDecodeError:
        raise RuntimeError("The AI service returned an invalid response.") from None

    try:
        parts = result["candidates"][0]["content"]["parts"]
        suggestions = "\n".join(part["text"] for part in parts if isinstance(part.get("text"), str))
    except (KeyError, IndexError, TypeError, AttributeError):
        raise RuntimeError("The AI service returned an unexpected response.") from None

    if not suggestions.strip():
        raise RuntimeError("The AI service did not return any suggestions.")

    return suggestions


def main():
    try:
        title = input("Title: ").strip()
        description = input("Description: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nTicket creation cancelled.", file=sys.stderr)
        return 1

    if not title:
        print("Title cannot be empty.", file=sys.stderr)
        return 1

    if not description:
        print("Description cannot be empty.", file=sys.stderr)
        return 1

    try:
        if TICKETS_FILE.exists():
            with TICKETS_FILE.open(encoding="utf-8") as file:
                tickets = json.load(file)
            if not isinstance(tickets, list):
                print("Error: tickets.json must contain a JSON array.", file=sys.stderr)
                return 1
        else:
            tickets = []

        ticket = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
        }
        tickets.append(ticket)

        with TICKETS_FILE.open("w", encoding="utf-8") as file:
            json.dump(tickets, file, indent=2, ensure_ascii=False)
            file.write("\n")
    except (OSError, json.JSONDecodeError) as error:
        print(f"Error saving ticket: {error}", file=sys.stderr)
        return 1

    print(f"Ticket created: {ticket['id']}")
    print(f"Description: {ticket['description']}")
    print("\nGetting AI suggestions...")
    try:
        suggestions = get_ai_suggestions(ticket["description"])
    except RuntimeError as error:
        print(f"AI suggestions unavailable: {error}", file=sys.stderr)
        return 0

    print("\nSuggestions:\n")
    print(suggestions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
