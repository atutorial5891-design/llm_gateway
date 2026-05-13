import getpass

from secrets_manager import SecretsManager


def main():
    secret_name = (
        input("Enter secret name [openai]: ")
        .strip()
        .lower()
        or "openai"
    )
    secret_value = getpass.getpass(
        f"Enter {secret_name} secret: "
    )

    SecretsManager.set_secret(
        secret_name,
        secret_value,
        context={
            "script": "save_secret.py",
            "entrypoint": "manual_prompt",
        },
    )

    print(
        f"{secret_name} secret stored securely in macOS Keychain"
    )


if __name__ == "__main__":
    main()