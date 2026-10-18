import os
from typing import Any

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # the quiz page must be able to call this from the browser
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Layer 1: defaults (lowest precedence) ----
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# ---- Layer 2: config.development.yaml (empty) ----
YAML_TEXT = ""

# ---- Layer 3: .env file ----
DOTENV_TEXT = "APP_PORT=8872\n"

# ---- Layer 4: OS env vars (APP_* prefix) ----
# Set here so the service behaves the same on any host.
os.environ.setdefault("APP_WORKERS", "16")
os.environ.setdefault("APP_LOG_LEVEL", "error")

ALIASES = {"num_workers": "workers"}   # NUM_WORKERS -> workers
INT_KEYS = {"port", "workers"}
TRUE_VALUES = {"true", "1", "yes", "on"}


def norm_key(raw: str) -> str:
    k = raw.strip()
    if k.upper().startswith("APP_"):
        k = k[4:]
    k = k.lower()
    return ALIASES.get(k, k)


def parse_dotenv(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[norm_key(k)] = v.strip().strip('"').strip("'")
    return out


def os_env_layer() -> dict:
    return {norm_key(k): v for k, v in os.environ.items() if k.startswith("APP_")}


def coerce(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        return int(str(value).strip())
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in TRUE_VALUES
    return str(value)


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/effective-config")
def effective_config(request: Request):
    cfg: dict = dict(DEFAULTS)                              # 1. defaults
    cfg.update({norm_key(k): v for k, v in (yaml.safe_load(YAML_TEXT) or {}).items()})  # 2. yaml
    cfg.update(parse_dotenv(DOTENV_TEXT))                   # 3. .env
    cfg.update(os_env_layer())                              # 4. OS env

    for item in request.query_params.getlist("set"):        # 5. CLI overrides
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        cfg[norm_key(k)] = v

    result = {}
    for key in ["port", "workers", "debug", "log_level", "api_key"]:
        result[key] = coerce(key, cfg[key])
    for key, value in cfg.items():                          # any extra keys, as strings
        if key not in result:
            result[key] = coerce(key, value)

    result["api_key"] = "****"                              # always masked
    return result
