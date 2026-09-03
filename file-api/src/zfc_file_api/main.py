from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("zfc_file_api.api:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
