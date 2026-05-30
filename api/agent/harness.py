import asyncio
import sys

from agent.loop import run_agent


async def main() -> None:
    chat_id = sys.argv[1] if len(sys.argv) > 1 else "harness-test-chat"
    print(f"Jonas agent harness (chat_id={chat_id}). Empty line  to quit.\n")
    while True:
        try:
            user_text = input("> ").strip()  # noqa
        except (EOFError, KeyboardInterrupt):
            break
        if not user_text:
            break
        calls: list = []
        result = await run_agent(user_text, chat_id=chat_id, record_calls=calls)
        for c in calls:
            print(f" \u2192 {c['name']}({c['input']}) -> {c['output']}")
        print(f"\n{result['final']}\n")


if __name__ == "__main__":
    asyncio.run(main())
