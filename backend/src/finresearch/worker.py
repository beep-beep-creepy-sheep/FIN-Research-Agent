from __future__ import annotations

import time

from finresearch.database.session import get_library_path
from finresearch.services.job_service import JobService


def run_once() -> dict[str, object] | None:
    return JobService(get_library_path()).run_next()


def main() -> None:
    while True:
        result = run_once()
        if result is None:
            time.sleep(2)
            continue
        print(result)


if __name__ == "__main__":
    main()

