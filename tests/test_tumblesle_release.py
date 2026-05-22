# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Tests for tumblesle_release."""

from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

from openqa_review import tumblesle_release  # SUT
from openqa_review.tumblesle_release import UnsupportedRsyncArgsError

# similar to python3.2 TemporaryDirectory, not available on older versions
# also see http://stackoverflow.com/a/13379969/5031322


@contextlib.contextmanager
def TemporaryDirectory() -> Generator[str, None, None]:  # noqa: N802
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@contextlib.contextmanager
def TumblesleDirectory(args: Namespace) -> Generator[str, None, None]:  # noqa: N802
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        args.src = str(tmp_path / "src") + "/"
        args.dest = str(tmp_path / "dest") + "/"
        # create a fake config entry
        args.config_path = str(tmp_path / "config_file")
        Path(args.config_path).write_text(
            """[Leap 42.2]
whitelist = arm7l-foo,bar@uefi""",
            encoding="utf-8",
        )

        # create some fake entries
        Path(args.src).mkdir()
        for d in ["iso", "hdd", "dest"]:
            Path(str(tmp_path / "src" / d)).mkdir()
        isos = [
            "iso/openSUSE-Leap-42.2-DVD-x86_64-Build0056-Media.iso",
            "iso/openSUSE-Leap-42.2-NET-x86_64-Build0052-Media.iso",
        ]
        hdds = [
            "hdd/opensuse-Tumbleweed-aarch64-20160626-gnome@aarch64.qcow2",
            "hdd/opensuse-42.2-x86_64-0056-gnome@64bit.qcow2",
        ]
        for asset in isos + hdds:
            (tmp_path / "src" / asset).touch()
        # The destination folder must exist
        Path(args.dest).mkdir()
        yield tmp_dir


@pytest.fixture
def args() -> Namespace:
    args = Namespace()
    args.verbose = 5
    args.dry_run = True
    args.dry_run_rsync = False
    args.config_path = "/tmp/this/file/does/not/exist"  # noqa: S108
    args.openqa_host = "https://openqa.opensuse.org"
    args.product = "Leap 42.2"
    args.group_id = 19
    args.check_against_build = "0046"
    args.whitelist = ""
    args.match = "open*-42.2*x86_64*"
    args.match_hdds = "*leap-42.2*x86_64*"
    args.check_build = "last"
    args.run_once = True
    args.release_file = ".release_info"
    args.sleeptime = 0
    args.load = True
    args.load_dir = Path(__file__).resolve().parent / "tumblesle/0046_0056_new_release"
    args.dest = "/tmp/"  # noqa: S108
    args.post_release_hook = None
    args.seen_maxlen = 1
    # Enable saving and disable loading if you want to add new test data downloaded from hosts
    #  args.save = True
    #  args.save_dir = args.load_dir
    return args


def test_help() -> None:
    sys.argv += ["--help"]
    with pytest.raises(SystemExit):
        tumblesle_release.main()


def test_compare_old_bad_against_new_good_yields_release(args: Namespace) -> None:
    args.match_hdds = None
    with TumblesleDirectory(args):
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == "0056"
        # same again, this time with rsync dry-run
        args.dry_run_rsync = True
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == "0056"
        # same again, this times 'hot'
        args.dry_run = False
        args.dry_run_rsync = False
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == "0056"
        args.post_release_hook = "/bin/true"
        # subsequent call with same build has same effect
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == "0056"


def test_specifying_more_recent_check_build_does_not_yield_release(args: Namespace) -> None:
    args.check_against_build = "0056"
    tr = tumblesle_release.TumblesleRelease(args)
    tr.one_run()
    assert tr.release_build is None


def test_compare_old_better_against_new_good_yields_regression(args: Namespace) -> None:
    args.check_against_build = "0052"
    args.load_dir = Path(__file__).resolve().parent / "tumblesle/0052_0056_regression"
    args.run_once = True
    tr = tumblesle_release.TumblesleRelease(args)
    tr.run()
    assert tr.release_build is None


def test_old_better_against_new_good_plus_whitelist_yields_forced_release(args: Namespace) -> None:
    args.check_against_build = "0052"
    args.load_dir = Path(__file__).resolve().parent / "tumblesle/0052_0056_regression"
    args.whitelist = "lxde@Laptop_64, DVD-x86_64-gnome@64bit, opensuse-42.2-NET-x86_64-gnome@64bit, \
            cryptlvm-image@uefi, gnome@Laptop_64, \
            sysauth_gnome@64bit, opensuse-42.2-NET-x86_64-RAID1@64bit"
    tr = tumblesle_release.TumblesleRelease(args)
    tr.check_last_builds()
    assert tr.release_build == "0056"


def test_select_different_build_checks_specified(args: Namespace) -> None:
    args.check_build = "0051"
    args.check_against_build = "0047"
    args.load_dir = Path(__file__).resolve().parent / "tumblesle/0047_0051_explicit_no_release"
    tr = tumblesle_release.TumblesleRelease(args)
    tr.check_last_builds()
    assert tr.release_build is None


def test_tagged_not_yet_implemented(args: Namespace) -> None:
    args.run_once = False
    args.check_against_build = "tagged"
    with pytest.raises(NotImplementedError):
        tumblesle_release.TumblesleRelease(args).run()


def test_unsafe_rsync_args_are_catched(args: Namespace) -> None:
    args.src = "/tmp/foo"  # noqa: S108
    with pytest.raises(UnsupportedRsyncArgsError):
        tumblesle_release.TumblesleRelease(args).run()


def test_compare_old_released_with_release_info_against_new_good_yields_release(args: Namespace) -> None:
    args.check_against_build = "release_info"
    with TumblesleDirectory(args), (Path(args.dest) / ".release_info").open("w", encoding="utf-8") as release_info:
        yaml.dump({args.product: {"build": "0046"}}, release_info)
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == "0056"


def test_softfailed_state_is_regarded_as_passed_with_newer_openqa(args: Namespace) -> None:
    args.load_dir = Path(__file__).resolve().parent / "tumblesle/0213_0215_new_openqa_with_softfailed"
    args.check_build = "0215"
    args.check_against_build = "0213"
    tr = tumblesle_release.TumblesleRelease(args)
    tr.check_last_builds()
    assert tr.release_build == "0215"


def test_notifications_are_sent(args: Namespace, mocker: MockerFixture) -> None:
    with TumblesleDirectory(args) as tmp_dir:
        config_path = Path(tmp_dir) / "config_file"
        with config_path.open("a", encoding="utf-8") as config:
            config.write(
                """
[notification]
host = localhost
"""
            )
        mocker.patch("pika.BlockingConnection")
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert '{"build": "0056"}' in tr.notify_seen
        # this will yield the same message and is therefore not sent out again
        tr.one_run()
        assert '{"build": "0056"}' in tr.notify_seen
