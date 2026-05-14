import argparse
import sys

from secrets_manager import SecretsManager


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read a secret from the keychain. "
            "By default prints a masked value only."
        ),
    )
    parser.add_argument(
        "secret_name",
        nargs="?",
        default="openai",
        help="Account name stored in keychain (default: openai). "
        "Names are case-insensitive when saved via save_secret.py "
        "(they are stored lowercase).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the full secret. Avoid in shared shells; "
        "may be captured in shell history.",
    )
    args = parser.parse_args()
    name = args.secret_name.strip().lower()
    if not name:
        parser.error("secret_name must not be empty")

    if args.full:
        value = SecretsManager.get_secret(name, masked=False)
        if value is None:
            print("Secret not set for this name.", file=sys.stderr)
            raise SystemExit(1)
        print(value)
        return

    value = SecretsManager.get_secret(name, masked=True)
    if value is None:
        print("(not set)")
        return
    print(value)


if __name__ == "__main__":
    main()
