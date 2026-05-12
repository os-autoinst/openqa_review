# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Pytest configuration and shared fixtures."""

import pytest
from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def mock_sleep(mocker: MockerFixture) -> None:
    mocker.patch("openqa_review.browser.time.sleep")
