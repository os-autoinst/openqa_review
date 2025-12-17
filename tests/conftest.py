import pytest


@pytest.fixture(autouse=True)
def mock_sleep(mocker) -> None:
    mocker.patch("openqa_review.browser.time.sleep")
