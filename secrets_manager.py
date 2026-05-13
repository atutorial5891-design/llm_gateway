import getpass
import inspect
import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import keyring
from keyring.errors import PasswordDeleteError


class SecretsManager:
    DEFAULT_SERVICE_NAME = "llm_gateway"
    DEFAULT_HOME_DIRECTORY = Path.home() / ".llm_gateway"
    SERVICE_NAME = os.getenv(
        "LLM_GATEWAY_SERVICE_NAME",
        DEFAULT_SERVICE_NAME,
    )
    HOME_DIRECTORY = Path(
        os.getenv(
            "LLM_GATEWAY_HOME",
            str(DEFAULT_HOME_DIRECTORY),
        )
    ).expanduser()
    LOG_DIRECTORY = Path(
        os.getenv(
            "LLM_GATEWAY_LOG_DIR",
            str(HOME_DIRECTORY / "logs"),
        )
    ).expanduser()
    LOG_FILE = LOG_DIRECTORY / "secrets_manager.log"
    LOG_RETENTION_DAYS = 15
    SUPPORTED_PROVIDERS = (
        "openai",
        "anthropic",
        "claude",
        "deepseek",
        "gemini",
        "openrouter",
        "groq",
        "mistral",
        "cohere",
        "together",
        "xai",
    )
    _LOGGER = None

    @staticmethod
    def _get_logger():
        if SecretsManager._LOGGER is None:
            SecretsManager.LOG_DIRECTORY.mkdir(
                parents=True,
                exist_ok=True,
            )
            logger = logging.getLogger(
                "llm_gateway.secrets_manager",
            )
            if not logger.handlers:
                handler = TimedRotatingFileHandler(
                    SecretsManager.LOG_FILE,
                    when="midnight",
                    interval=1,
                    backupCount=SecretsManager.LOG_RETENTION_DAYS,
                    encoding="utf-8",
                )
                handler.setFormatter(
                    logging.Formatter("%(message)s"),
                )
                logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
            SecretsManager._LOGGER = logger
        return SecretsManager._LOGGER

    @staticmethod
    def _validate_secret_name(secret_name):
        normalized_name = str(secret_name).strip()
        if not normalized_name:
            raise ValueError("secret_name must not be empty")
        return normalized_name

    @staticmethod
    def _normalize_provider_name(provider_name):
        return SecretsManager._validate_secret_name(
            provider_name,
        ).lower()

    @staticmethod
    def _mask_secret(secret_value):
        if secret_value is None:
            return None
        secret_text = str(secret_value)
        if not secret_text:
            return ""
        if len(secret_text) <= 8:
            return "*" * len(secret_text)
        return (
            f"{secret_text[:4]}..."
            f"{secret_text[-4:]}"
        )

    @staticmethod
    def _serialize_log_value(value):
        if value is None:
            return None
        if isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {
                str(key): SecretsManager._serialize_log_value(val)
                for key, val in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [
                SecretsManager._serialize_log_value(item)
                for item in value
            ]
        return repr(value)

    @staticmethod
    def _get_caller_info():
        current_file = Path(__file__).resolve()
        frame = inspect.currentframe()
        try:
            caller_frame = None
            if frame is not None:
                caller_frame = frame.f_back
            while caller_frame is not None:
                caller_path = Path(
                    caller_frame.f_code.co_filename,
                ).resolve()
                if caller_path != current_file:
                    return {
                        "module": caller_frame.f_globals.get(
                            "__name__"
                        ),
                        "function": caller_frame.f_code.co_name,
                        "file": str(caller_path),
                        "line": caller_frame.f_lineno,
                    }
                caller_frame = caller_frame.f_back
        finally:
            del frame
        return None

    @staticmethod
    def _log_call(
        action,
        api_method,
        secret_name,
        *,
        secret_value=None,
        returned_value=None,
        masked=False,
        status="success",
        context=None,
        error=None,
    ):
        log_record = {
            "timestamp": datetime.now(
                timezone.utc,
            ).isoformat(),
            "service_name": SecretsManager.SERVICE_NAME,
            "action": action,
            "api_method": api_method,
            "secret_name": secret_name,
            "secret_value_masked": SecretsManager._mask_secret(
                secret_value,
            ),
            "secret_length": (
                len(str(secret_value))
                if secret_value is not None
                else None
            ),
            "returned_value_masked": (
                returned_value
                if masked
                else SecretsManager._mask_secret(
                    returned_value,
                )
            ),
            "returned_masked": masked,
            "status": status,
            "caller": SecretsManager._get_caller_info(),
            "context": SecretsManager._serialize_log_value(
                context,
            ),
            "runtime": {
                "user": getpass.getuser(),
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
            },
        }
        if error is not None:
            log_record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }

        SecretsManager._get_logger().info(
            json.dumps(
                log_record,
                sort_keys=True,
            )
        )

    @staticmethod
    def _get_secret(
        secret_name,
        *,
        masked=False,
        context=None,
        api_method="get_secret",
    ):
        validated_name = SecretsManager._validate_secret_name(
            secret_name,
        )
        try:
            secret_value = keyring.get_password(
                SecretsManager.SERVICE_NAME,
                validated_name,
            )
            returned_value = (
                SecretsManager._mask_secret(secret_value)
                if masked
                else secret_value
            )
            status = (
                "not_found"
                if secret_value is None
                else "success"
            )
            SecretsManager._log_call(
                "get",
                api_method,
                validated_name,
                secret_value=secret_value,
                returned_value=returned_value,
                masked=masked,
                status=status,
                context=context,
            )
            return returned_value
        except Exception as exc:
            SecretsManager._log_call(
                "get",
                api_method,
                validated_name,
                masked=masked,
                status="error",
                context=context,
                error=exc,
            )
            raise

    @staticmethod
    def _set_secret(
        secret_name,
        secret_value,
        *,
        context=None,
        api_method="set_secret",
    ):
        validated_name = SecretsManager._validate_secret_name(
            secret_name,
        )
        try:
            keyring.set_password(
                SecretsManager.SERVICE_NAME,
                validated_name,
                secret_value,
            )
            SecretsManager._log_call(
                "set",
                api_method,
                validated_name,
                secret_value=secret_value,
                status="success",
                context=context,
            )
        except Exception as exc:
            SecretsManager._log_call(
                "set",
                api_method,
                validated_name,
                secret_value=secret_value,
                status="error",
                context=context,
                error=exc,
            )
            raise

    @staticmethod
    def _delete_secret(
        secret_name,
        *,
        context=None,
        api_method="delete_secret",
    ):
        validated_name = SecretsManager._validate_secret_name(
            secret_name,
        )
        try:
            keyring.delete_password(
                SecretsManager.SERVICE_NAME,
                validated_name,
            )
            SecretsManager._log_call(
                "delete",
                api_method,
                validated_name,
                status="success",
                context=context,
            )
        except PasswordDeleteError as exc:
            SecretsManager._log_call(
                "delete",
                api_method,
                validated_name,
                status="not_found",
                context=context,
                error=exc,
            )
            raise
        except Exception as exc:
            SecretsManager._log_call(
                "delete",
                api_method,
                validated_name,
                status="error",
                context=context,
                error=exc,
            )
            raise

    @staticmethod
    def get_secret(secret_name, masked=False, context=None):
        return SecretsManager._get_secret(
            secret_name,
            masked=masked,
            context=context,
            api_method="get_secret",
        )

    @staticmethod
    def set_secret(secret_name, secret_value, context=None):
        SecretsManager._set_secret(
            secret_name,
            secret_value,
            context=context,
            api_method="set_secret",
        )

    @staticmethod
    def delete_secret(secret_name, context=None):
        SecretsManager._delete_secret(
            secret_name,
            context=context,
            api_method="delete_secret",
        )

    @staticmethod
    def get_provider_key(
        provider_name,
        masked=False,
        context=None,
    ):
        return SecretsManager._get_secret(
            SecretsManager._normalize_provider_name(
                provider_name,
            ),
            masked=masked,
            context=context,
            api_method="get_provider_key",
        )

    @staticmethod
    def set_provider_key(provider_name, api_key, context=None):
        SecretsManager._set_secret(
            SecretsManager._normalize_provider_name(
                provider_name,
            ),
            api_key,
            context=context,
            api_method="set_provider_key",
        )

    @staticmethod
    def delete_provider_key(provider_name, context=None):
        SecretsManager._delete_secret(
            SecretsManager._normalize_provider_name(
                provider_name,
            ),
            context=context,
            api_method="delete_provider_key",
        )

    @staticmethod
    def get_openai_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "openai",
            masked=masked,
            context=context,
            api_method="get_openai_key",
        )

    @staticmethod
    def set_openai_key(api_key, context=None):
        SecretsManager._set_secret(
            "openai",
            api_key,
            context=context,
            api_method="set_openai_key",
        )

    @staticmethod
    def delete_openai_key(context=None):
        SecretsManager._delete_secret(
            "openai",
            context=context,
            api_method="delete_openai_key",
        )

    @staticmethod
    def get_anthropic_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "anthropic",
            masked=masked,
            context=context,
            api_method="get_anthropic_key",
        )

    @staticmethod
    def set_anthropic_key(api_key, context=None):
        SecretsManager._set_secret(
            "anthropic",
            api_key,
            context=context,
            api_method="set_anthropic_key",
        )

    @staticmethod
    def delete_anthropic_key(context=None):
        SecretsManager._delete_secret(
            "anthropic",
            context=context,
            api_method="delete_anthropic_key",
        )

    @staticmethod
    def get_claude_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "claude",
            masked=masked,
            context=context,
            api_method="get_claude_key",
        )

    @staticmethod
    def set_claude_key(api_key, context=None):
        SecretsManager._set_secret(
            "claude",
            api_key,
            context=context,
            api_method="set_claude_key",
        )

    @staticmethod
    def delete_claude_key(context=None):
        SecretsManager._delete_secret(
            "claude",
            context=context,
            api_method="delete_claude_key",
        )

    @staticmethod
    def get_deepseek_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "deepseek",
            masked=masked,
            context=context,
            api_method="get_deepseek_key",
        )

    @staticmethod
    def set_deepseek_key(api_key, context=None):
        SecretsManager._set_secret(
            "deepseek",
            api_key,
            context=context,
            api_method="set_deepseek_key",
        )

    @staticmethod
    def delete_deepseek_key(context=None):
        SecretsManager._delete_secret(
            "deepseek",
            context=context,
            api_method="delete_deepseek_key",
        )

    @staticmethod
    def get_gemini_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "gemini",
            masked=masked,
            context=context,
            api_method="get_gemini_key",
        )

    @staticmethod
    def set_gemini_key(api_key, context=None):
        SecretsManager._set_secret(
            "gemini",
            api_key,
            context=context,
            api_method="set_gemini_key",
        )

    @staticmethod
    def delete_gemini_key(context=None):
        SecretsManager._delete_secret(
            "gemini",
            context=context,
            api_method="delete_gemini_key",
        )

    @staticmethod
    def get_openrouter_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "openrouter",
            masked=masked,
            context=context,
            api_method="get_openrouter_key",
        )

    @staticmethod
    def set_openrouter_key(api_key, context=None):
        SecretsManager._set_secret(
            "openrouter",
            api_key,
            context=context,
            api_method="set_openrouter_key",
        )

    @staticmethod
    def delete_openrouter_key(context=None):
        SecretsManager._delete_secret(
            "openrouter",
            context=context,
            api_method="delete_openrouter_key",
        )

    @staticmethod
    def get_groq_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "groq",
            masked=masked,
            context=context,
            api_method="get_groq_key",
        )

    @staticmethod
    def set_groq_key(api_key, context=None):
        SecretsManager._set_secret(
            "groq",
            api_key,
            context=context,
            api_method="set_groq_key",
        )

    @staticmethod
    def delete_groq_key(context=None):
        SecretsManager._delete_secret(
            "groq",
            context=context,
            api_method="delete_groq_key",
        )

    @staticmethod
    def get_mistral_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "mistral",
            masked=masked,
            context=context,
            api_method="get_mistral_key",
        )

    @staticmethod
    def set_mistral_key(api_key, context=None):
        SecretsManager._set_secret(
            "mistral",
            api_key,
            context=context,
            api_method="set_mistral_key",
        )

    @staticmethod
    def delete_mistral_key(context=None):
        SecretsManager._delete_secret(
            "mistral",
            context=context,
            api_method="delete_mistral_key",
        )

    @staticmethod
    def get_cohere_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "cohere",
            masked=masked,
            context=context,
            api_method="get_cohere_key",
        )

    @staticmethod
    def set_cohere_key(api_key, context=None):
        SecretsManager._set_secret(
            "cohere",
            api_key,
            context=context,
            api_method="set_cohere_key",
        )

    @staticmethod
    def delete_cohere_key(context=None):
        SecretsManager._delete_secret(
            "cohere",
            context=context,
            api_method="delete_cohere_key",
        )

    @staticmethod
    def get_together_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "together",
            masked=masked,
            context=context,
            api_method="get_together_key",
        )

    @staticmethod
    def set_together_key(api_key, context=None):
        SecretsManager._set_secret(
            "together",
            api_key,
            context=context,
            api_method="set_together_key",
        )

    @staticmethod
    def delete_together_key(context=None):
        SecretsManager._delete_secret(
            "together",
            context=context,
            api_method="delete_together_key",
        )

    @staticmethod
    def get_xai_key(masked=False, context=None):
        return SecretsManager._get_secret(
            "xai",
            masked=masked,
            context=context,
            api_method="get_xai_key",
        )

    @staticmethod
    def set_xai_key(api_key, context=None):
        SecretsManager._set_secret(
            "xai",
            api_key,
            context=context,
            api_method="set_xai_key",
        )

    @staticmethod
    def delete_xai_key(context=None):
        SecretsManager._delete_secret(
            "xai",
            context=context,
            api_method="delete_xai_key",
        )
