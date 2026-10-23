"""Explicitly start HANNI's single configured local assistant model."""
from __future__ import annotations

import argparse
import os
import time
from dotenv import load_dotenv
from hanni.config.loader import load_config
from hanni.dashboard.launcher import start_model, stop_owned


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-id', default=None, help='configured model id (normally the single Supervisor)')
    parser.add_argument('--model-file', default=None)
    args = parser.parse_args(argv)
    load_dotenv(override=False)
    config = load_config()
    model_id = args.model_id or config.models.supervisor.id
    if model_id != config.models.supervisor.id:
        parser.error(f"HANNI is single-model; configured assistant id is {config.models.supervisor.id!r}")
    process = None
    try:
        process = start_model(config, model_id=model_id,
                              model_file=args.model_file or os.getenv('HANNI_MODEL_FILE'))
        print(f'{model_id} ready. Ctrl+C stops this owned server.', flush=True)
        while process.poll() is None:
            time.sleep(.5)
        return process.returncode
    except KeyboardInterrupt:
        return 0
    finally:
        stop_owned(process)


if __name__ == '__main__':
    raise SystemExit(main())
