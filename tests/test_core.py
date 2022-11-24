"""Core tests."""


def test_run_async() -> None:
    """Test run async functions."""
    from asyncio import sleep
    from aio_lambda_api import Handler

    async def test() -> int:
        """Test."""
        await sleep(0.0001)
        return 1

    assert Handler().run_async(test()) == 1
