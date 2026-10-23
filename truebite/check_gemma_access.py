
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).with_name(".env"))


def main() -> int:
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    if not api_key:
        print("GOOGLE_API_KEY is missing. Configure it in truebite/.env.")
        return 1

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: TrueBite connection successful",
        )
    except Exception as exc:
        print(
            f"Text API check failed ({type(exc).__name__}). "
            "Verify the model ID, account access, network and quota."
        )
        return 1

    if not getattr(response, "text", None):
        print("The configured model returned no readable text.")
        return 1
    print(f"Text API check succeeded for configured model: {model}")
    print("Image input is not checked by this command; use the app to test it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
