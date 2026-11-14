# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Pytest configuration and shared fixtures."""

from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

import openqa_review.browser


@pytest.fixture(autouse=True)
def mock_sleep(mocker: MockerFixture) -> None:
    mocker.patch.object(openqa_review.browser, "time", SimpleNamespace(sleep=mocker.Mock()))
