from __future__ import annotations

import asyncio

from app.telegram import run


async def main() -> None:
    await run()


if __name__ == "__main__":
    asyncio.run(main())
