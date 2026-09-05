from .agent import create_agent


def main() -> None:
    agent = create_agent()

    prompt = input("Ask Cosmic Explorer: ").strip()

    if not prompt:
        print("Please enter a question.")
        return

    result = agent(prompt)
    print(result)