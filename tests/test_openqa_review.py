# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Tests for openqa_review."""

from __future__ import annotations

import contextlib
import re
import shutil
import sys
import tempfile
from argparse import Namespace
from configparser import ConfigParser
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, call
from urllib.parse import urljoin

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

from openqa_review import openqa_review  # SUT
from openqa_review.browser import Browser, BugzillaError, DownloadError


def args_factory() -> Namespace:
    args = Namespace()
    args.host = "https://openqa.opensuse.org"
    args.job_group_urls = None
    args.job_groups = None
    args.exclude_job_groups = None
    args.no_progress = True
    args.verbose = 1
    args.output_state_results = False
    args.base_url = "/"
    args.verbose_test = 4
    args.arch = "x86_64"
    args.save = False
    args.load = False
    args.load_dir = "."
    args.builds = None
    args.against_reviewed = None
    args.running_threshold = 0
    args.show_empty = True
    args.bugrefs = False
    args.include_softfails = True
    args.short_failure_str = False
    args.abbreviate_test_issues = False
    args.query_issue_status = False
    args.query_issue_status_help = True
    args.report_links = False
    args.skip_passed = False
    args.todo_only = False
    args.min_days_unchanged = openqa_review.MIN_DAYS_UNCHANGED
    args.ignore_pattern = openqa_review.NO_REMINDER_REGEX
    args.no_exponential_backoff = False
    args.reopen = "none"
    return args


def browser_factory(args: Namespace | None = None) -> Browser:
    if not args:
        args = cache_test_args_factory()
    return openqa_review.Browser(args, urljoin(args.host, args.base_url))


# similar to python3.2 TemporaryDirectory, not available on older versions
# also see http://stackoverflow.com/a/13379969/5031322


@contextlib.contextmanager
def TemporaryDirectory() -> Generator[str, None, None]:  # noqa: N802
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_help() -> None:
    sys.argv += ["--help"]
    with pytest.raises(SystemExit):
        openqa_review.main()


def test_missing_config() -> None:
    openqa_review.CONFIG_PATH = "/dev/null/.missing_file"
    sys.argv[1:] = ["--query-issue-status"]
    with pytest.raises(SystemExit) as excinfo:
        openqa_review.main()
    assert excinfo.value.code == 1


def test_query_issue_status_help_shows_config_help() -> None:
    sys.argv[1:] = ["--query-issue-status-help"]
    with pytest.raises(SystemExit):
        # we are not actually testing the content of help, just that it does not fail
        openqa_review.main()


def test_args_implicit() -> None:
    sys.argv[1:] = ["--reminder-comment-on-issues"]
    args = openqa_review.parse_args()
    assert args.reminder_comment_on_issues
    assert args.query_issue_status
    assert args.bugrefs

    sys.argv[1:] = ["--report-links"]
    args = openqa_review.parse_args()
    assert not args.bugrefs


def test_args_reminder() -> None:
    sys.argv[1:] = ["--reminder-comment-on-issues", "--no-reminder-on", "pattern"]
    args = openqa_review.parse_args()
    assert args.reminder_comment_on_issues
    assert args.ignore_pattern == re.compile(r"pattern")


def cache_test_args_factory() -> Namespace:
    args = args_factory()
    args.job_group_urls = args.host + "/group_overview/25"
    args.load = True
    args.load_dir = Path(__file__).resolve().parent
    return args


def compare_report(report: str, ref_report_path: Path) -> None:
    # If the reference report should be written initially or updated one can just write the report as string to file
    # Path(ref_report_path).write_text(str(report), encoding="utf-8")
    ref_report = Path(ref_report_path).read_text(encoding="utf-8")
    # for simpler display of the diff in case of differences it helps to have
    # both reports in same encoding, i.e. casting to str
    lines = str(report).splitlines()
    ref = ref_report.splitlines()
    # report equals the reference except for the time tag so skip the
    # date/time line
    del lines[3], ref[3]
    assert lines == ref


def test_previously_loaded_cache_file_is_generated_into_valid_verbose_report_if_configured() -> None:
    args = cache_test_args_factory()
    report = str(openqa_review.generate_report(args))
    assert "**Common issues:**" in report
    # Missing architecture is reported
    assert re.search(r"Missing arch.*i586", report)
    compare_report(report, Path(__file__).resolve().parent / "report25_TTT.md")


def test_previously_loaded_cache_file_is_generated_into_valid_terse_report_by_default() -> None:
    args = cache_test_args_factory()
    args.verbose_test = 1
    report = str(openqa_review.generate_report(args))
    assert "**Common issues:**" in report
    compare_report(report, Path(__file__).resolve().parent / "report25_terse.md")


def test_previously_loaded_cache_file_is_generated_into_ref_report_l2() -> None:
    args = cache_test_args_factory()
    args.verbose_test = 2
    report = str(openqa_review.generate_report(args))
    compare_report(report, Path(__file__).resolve().parent / "report25_T.md")


def test_previously_loaded_cache_file_is_generated_into_ref_report_l3() -> None:
    args = cache_test_args_factory()
    args.verbose_test = 3
    report = str(openqa_review.generate_report(args))
    compare_report(report, Path(__file__).resolve().parent / "report25_TT.md")


def test_builds_can_be_specified_and_appear_in_report() -> None:
    args = cache_test_args_factory()
    args.builds = "0313,0308"
    report = str(openqa_review.generate_report(args))
    assert "**Build:** {} (reference {})".format(*args.builds.split(",")) in report


def test_too_high_verbosity_selection_yields_still_valid_selection() -> None:
    args = cache_test_args_factory()
    args.verbose_test = 5
    report = str(openqa_review.generate_report(args))
    assert report


def test_ha_tests_yields_valid_report_with_valid_build_nr() -> None:
    args = cache_test_args_factory()
    args.arch = None  # let this test check architectures by itself to reach good test coverage
    args.load_dir = Path(__file__).resolve().parent / "live"
    args.job_group_urls = args.host + "/group_overview/27"
    report = str(openqa_review.generate_report(args))
    assert "0104@0351" in report


def test_specified_job_group_yields_single_product_report() -> None:
    args = cache_test_args_factory()
    args.job_group_urls = None
    args.load_dir = Path(__file__).resolve().parent / "single_job_group"
    args.job_groups = "openSUSE Argon"
    report = str(openqa_review.generate_report(args))
    assert args.job_groups in report
    # There must be only one job group tag
    assert len([line for line in report.splitlines() if line.startswith("#")]) == 1

    # Invalid name should yield assertion with helpful message
    args.job_groups = "openSUSE Tumbleweed FOO"
    with pytest.raises(AssertionError) as e:
        report = openqa_review.generate_report(args)
    assert "No job group" in str(e.value)

    # Multiple job groups can be specified
    args.job_groups = "openSUSE Argon,openSUSE Leap 42.2 Updates"
    # we don't actually need to check the parsing just make sure
    # openqa_review tries to parse all and as there is no cache page
    # for 'openSUSE Tumbleweed  2.KDE' saved, we assume its corresponding
    # page can not be retrieved.
    # Unfortunately we can not easily be more specific about the
    # exception as python2 raises IOError, python3 FileNotFoundError
    # but we can check the content anyway.
    with pytest.raises(Exception) as e:
        report = str(openqa_review.generate_report(args))
    assert "group_overview:26" in str(e.value)

    # job groups can also be used as an incomplete search tags or regex
    args.job_groups = "(42.2 Updates|Argon)"
    # To increase statement and branch coverage we enable progress report here.
    # It will be invisible but executed.
    args.no_progress = False
    # see above
    with pytest.raises(Exception) as e:
        report = str(openqa_review.generate_report(args))
    assert "group_overview:26" in str(e.value)

    # job group with only a single recent build yields empty report
    args.job_groups = "openSUSE Leap 42.2 AArch64"
    report = str(openqa_review.generate_report(args))
    assert args.job_groups in report
    # There must be only one job group tag
    assert "Not enough finished builds" in report


def test_new_job_group_json_syntax_after_openqa_9b50b22() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "job_group_after_openqa_9b50b22"
    args.job_group_urls = "http://openqa.opensuse.org/group_overview/70"
    report = str(openqa_review.generate_report(args))
    assert "0211" in report
    assert "Green" in report


def test_openqa_45_bootstrap_4_can_parse_failed_modules() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "openqa_4.5_dashboard"
    args.job_group_urls = "https://openqa.opensuse.org/group_overview/41"
    report = str(openqa_review.generate_report(args))
    assert "20180424" in report
    assert "installation" in report


def test_get_build_urls_to_compare_finds_last_reviewed_if_selected() -> None:
    args = cache_test_args_factory()
    browser = browser_factory(args)
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed="0311")
    assert "=0311" in current
    assert "=0307" in reviewed

    # If '--against-reviewed' is 'last', search for the latest finished
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed="last")
    assert "=0313" in current
    assert "=0307" in reviewed

    # Also accept still running if threshold is increased
    current, reviewed = openqa_review.get_build_urls_to_compare(
        browser, args.job_group_urls, against_reviewed="last", running_threshold=45
    )
    assert "=0318" in current
    assert "=0307" in reviewed

    # Not accepted if slightly below threshold
    current, reviewed = openqa_review.get_build_urls_to_compare(
        browser, args.job_group_urls, against_reviewed="last", running_threshold=36
    )
    assert "=0313" in current
    assert "=0307" in reviewed


def test_non_number_build_nr_also_finds_valid_review_build_urls() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "live"
    args.job_group_urls = args.host + "/group_overview/27"
    browser = browser_factory(args)
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed="last")
    assert "=0104%400351" in current  # i.e. escaped '0104@0351'
    assert "=0097%400305" in reviewed

    # if no review comments are found we revert to the last two finished
    args.load_dir = Path(__file__).resolve().parent / "live_no_review"
    browser = browser_factory(args)
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed="last")
    assert "=0104%400351" in current  # i.e. escaped '0104@0351'
    assert "=0104%400350" in reviewed  # no review comments found, reverting to last two finished

    # builds with no finished results are catched
    args.load_dir = Path(__file__).resolve().parent / "only_old_invalid_builds"
    args.job_group_urls = args.host + "/group_overview/28"
    browser = browser_factory(args)
    with pytest.raises(openqa_review.NotEnoughBuildsError):
        current, reviewed = openqa_review.get_build_urls_to_compare(
            browser, args.job_group_urls, against_reviewed="last"
        )


def test_also_dotted_builds_can_be_specified_and_appear_in_report() -> None:
    args = cache_test_args_factory()
    args.job_group_urls = args.host + "/group_overview/26"
    browser = browser_factory(args)
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed="last")
    assert "=170.1" in current
    assert "=162.2" in reviewed


def test_builds_with_lower_number_but_more_recent_version_get_compared_correctly() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "multi_version"
    args.job_group_urls = "http://openqa.suse.de/group_overview/139"
    browser = browser_factory(args)
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls)
    assert "=0109" in current
    assert "=0456" in reviewed


def test_generate_report_with_progress_notification_does_not_fail() -> None:
    args = cache_test_args_factory()
    # Not easy to test automatically but at least we can call it and assume it also gives valid results
    args.no_progress = False
    args.job_groups_url = None
    report = str(openqa_review.generate_report(args))
    assert "**Common issues:**" in report


def test_state_report_does_not_break_generation() -> None:
    args = cache_test_args_factory()
    args.output_state_results = True
    report = openqa_review.generate_report(args)
    assert report


def test_get_job_groups_yields_job_groups_in_page() -> None:
    args = cache_test_args_factory()
    args.job_groups = None
    args.job_group_urls = None
    args.load_dir = Path(__file__).resolve().parent / "single_job_group"
    root_url = urljoin(args.host, args.base_url)
    browser = browser_factory(args)
    job_groups = openqa_review.get_job_groups(browser, root_url, args)
    assert len(job_groups.keys()) == 14
    args.load_dir = Path(__file__).resolve().parent / "openqa_4.4_dashboard"
    browser = browser_factory(args)
    job_groups = openqa_review.get_job_groups(browser, root_url, args)
    assert sorted(job_groups.keys()) == sorted([
        "Staging Projects",
        "Test Parent Group / openSUSE Argon",
        "openSUSE Krypton",
        "openSUSE Leap 42.1 JeOS",
        "openSUSE Leap 42.1 Maintenance",
        "openSUSE Leap 42.1 Updates",
        "openSUSE Leap 42.2",
        "openSUSE Leap 42.2 AArch64",
        "openSUSE Leap 42.2 Maintenance",
        "openSUSE Leap 42.2 Updates",
        "openSUSE Leap Staging Projects",
        "openSUSE Tumbleweed",
        "openSUSE Tumbleweed AArch64",
        "openSUSE Tumbleweed PowerPC",
    ])
    args.exclude_job_groups = "(Krypton|Leap)"
    job_groups = openqa_review.get_job_groups(browser, root_url, args)
    assert sorted(job_groups.keys()) == sorted([
        "Staging Projects",
        "Test Parent Group / openSUSE Argon",
        "openSUSE Tumbleweed",
        "openSUSE Tumbleweed AArch64",
        "openSUSE Tumbleweed PowerPC",
    ])


def test_single_job_group_pages_can_be_cached_from_cache() -> None:
    args = cache_test_args_factory()
    with TemporaryDirectory() as tmp_dir:
        args.save_dir = tmp_dir
        args.save = True
        report = str(openqa_review.generate_report(args))
        assert "**Common issues:**" in report


def test_new_tests_appearing_in_builds_are_supported() -> None:
    args = cache_test_args_factory()
    args.job_groups = None
    args.builds = "0405,0389"
    args.arch = "i586"
    args.running_threshold = 10
    args.load_dir = Path(__file__).resolve().parent / "differing_tests"
    report = str(openqa_review.generate_report(args))
    # There should be one new test which is failing and has not been there in before
    assert '* [btrfs@zkvm](https://openqa.opensuse.org/tests/181148 "Failed modules: livecdreboot")' in report


def test_skip_passed() -> None:
    args = cache_test_args_factory()
    args.skip_passed = True
    args.show_empty = False
    args.job_groups = ["openSUSE Tumbleweed WSL", "openSUSE Tumbleweed PowerPC"]
    args.load_dir = Path(__file__).resolve().parent / "skip-passed"
    args.job_group_urls = "https://openqa.opensuse.org/group_overview/68,https://openqa.opensuse.org/group_overview/4"
    args.arch = None
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report-68-4.md")


def test_todo_only() -> None:
    args = cache_test_args_factory()
    args.todo_only = True
    args.show_empty = False
    args.load_dir = Path(__file__).resolve().parent / "todo-only"
    args.job_group_urls = ",".join(f"https://openqa.opensuse.org/group_overview/{i}" for i in (2, 24, 35))
    args.arch = None
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report-todo-only.md")


def bugrefs_test_args_factory() -> Namespace:
    args = cache_test_args_factory()
    args.job_groups = None
    args.bugrefs = True
    args.builds = "1507,1500"
    args.arch = "i586"
    args.load_dir = Path(__file__).resolve().parent / "tags_labels"
    args.show_empty = False
    args.include_softfails = False
    args.verbose_test = 2
    openqa_review.config = ConfigParser()
    openqa_review.config.add_section("product_issues")
    openqa_review.config.set("product_issues", "base_url", "https://apibugzilla.suse.com")
    openqa_review.config.set("product_issues", "username", "user")
    openqa_review.config.set("product_issues", "password", "pass")
    openqa_review.config.set("product_issues", "report_url", "https://bugzilla.opensuse.org")
    openqa_review.config.add_section("product_issues:https://openqa.opensuse.org:product_mapping")
    openqa_review.config.set("product_issues:https://openqa.opensuse.org:product_mapping", "25", "openSUSE Tumbleweed")
    openqa_review.config.add_section("product_issues:https://openqa.opensuse.org:component_mapping")
    openqa_review.config.set(
        "product_issues:https://openqa.opensuse.org:component_mapping", "installation-bootloader", "Bootloader"
    )
    openqa_review.config.add_section("test_issues")
    openqa_review.config.set("test_issues", "api_key", "0123456789ABCDEF")
    openqa_review.config.set(
        "test_issues", "report_url", "https://progress.opensuse.org/projects/openqatests/issues/new"
    )
    return args


def test_bugrefs_are_used_for_triaging() -> None:
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    report = str(openqa_review.generate_report(args))
    # report should feature bug references
    assert "bsc#" in report
    # and references to 'test issues'
    assert "poo#" in report
    compare_report(report, args.load_dir / "report25_bugrefs.md")


def test_bugrefs_with_abbreviated_format_can_be_used() -> None:
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.short_failure_str = True
    args.abbreviate_test_issues = True
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_bugrefs_abbreviated.md")


def test_bugrefs_with_report_links() -> None:
    args = bugrefs_test_args_factory()
    args.report_links = True
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_T_bugrefs.md")


def test_bugrefs_including_softfails() -> None:
    args = bugrefs_test_args_factory()
    args.include_softfails = True
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_T_bugrefs_softfails.md")


def test_bugrefs_with_report_links_new_issue() -> None:
    args = bugrefs_test_args_factory()
    args.report_links = True
    args.include_softfails = False
    args.load_dir = Path(__file__).resolve().parent / "tags_labels/report_link_new_issue"
    args.arch = "arm"
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_bugrefs_bug_link_new_issue.md")


def test_issue_status_can_be_queried_from_bugrefs() -> None:
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.query_issue_status = True
    args.include_softfails = True
    args.load_dir = Path(__file__).resolve().parent / "tags_labels"
    args.arch = "i586"
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_bugrefs_query_issues.md")
    # report generated when no todo items are left and some bugref is not accessible
    args.builds = "1508,1500"
    args.include_softfails = False
    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report25_bugrefs_build1508.md")


def test_reminder_comments_on_referenced_bugs_are_posted() -> None:
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.query_issue_status = True
    args.dry_run = True
    args.include_softfails = True
    args.reopen = "all"
    report = openqa_review.generate_report(args)

    # test double comment prevention code
    p, pr = next(iter(report.report.items()))
    report.report[p + 237] = pr

    openqa_review.reminder_comment_on_issues(report, args)
    args.dry_run = False


def test_reminder_comments_on_referenced_bugs_are_not_duplicated(mocker: MockerFixture) -> None:
    browser_mock = mocker.patch.object(Browser, "json_rpc_post")
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.query_issue_status = True
    args.dry_run = True
    args.include_softfails = True
    args.reopen = "none"
    args.load_dir = Path(__file__).resolve().parent / "without_duplicates"
    report = openqa_review.generate_report(args)
    openqa_review.reminder_comment_on_issues(report, args)
    args.dry_run = False
    browser_mock.assert_not_called()


def test_reminder_comments_are_ignored_on_no_reminder(mocker: MockerFixture) -> None:
    browser_mock = mocker.patch.object(Browser, "json_rpc_post")
    args = bugrefs_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "softfails"
    args.verbose_test = 1
    args.dry_run = True
    args.include_softfails = True
    args.query_issue_status = True
    report = openqa_review.generate_report(args)
    # there should be no comment with default WONTFIX|NO_REMINDER softfail pattern
    openqa_review.reminder_comment_on_issues(report, args)
    browser_mock.assert_not_called()
    # without a match on the pattern, there shall be one reminder
    args.ignore_pattern = re.compile(r"THIS_WILL_NOT_MATCH")
    args.reopen = "none"
    openqa_review.reminder_comment_on_issues(report, args)
    browser_mock.assert_not_called()
    args.reopen = "all"
    openqa_review.reminder_comment_on_issues(report, args)
    browser_mock.assert_called_once()
    args.dry_run = False


def test_reminder_comments_includes_link_to_failed_step(mocker: MockerFixture) -> None:
    browser_mock = mocker.patch.object(Browser, "json_rpc_post")
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.dry_run = True
    args.include_softfails = True
    args.query_issue_status = True
    args.reopen = "all"
    report = openqa_review.generate_report(args)
    openqa_review.reminder_comment_on_issues(report, args)
    # there should be comments, the second one is interesting
    browser_mock.assert_called()
    call_name, call_args, call_kwargs = browser_mock.mock_calls[1]
    assert call_args[1] == "Bug.update"
    # comment should include link to a test
    comment = call_args[2]["comment"]["body"]
    assert re.search(r"https://openqa.opensuse.org/tests/\d+", comment)
    # the link should also include the failed step
    assert re.search(r"https://openqa.opensuse.org/tests/384333/modules/xterm/steps/7", comment)
    args.dry_run = False


def test_custom_reports_based_on_issue_status() -> None:
    args = bugrefs_test_args_factory()
    args.verbose_test = 1
    args.query_issue_status = True
    args.include_softfails = True
    # now, try filtering: unassigned
    report = openqa_review.generate_report(args)
    openqa_review.filter_report(report, openqa_review.ie_filters["unassigned"])
    compare_report(str(report), args.load_dir / "report25_bugrefs_query_issues_filter_unassigned.md")

    # 2nd filter: closed
    report = openqa_review.generate_report(args)
    openqa_review.filter_report(report, openqa_review.ie_filters["closed"])
    compare_report(str(report), args.load_dir / "report25_bugrefs_query_issues_filter_closed.md")


def test_get_bugref_for_softfailed_module() -> None:
    args = cache_test_args_factory()
    args.verbose_test = 1
    args.show_empty = False
    args.bugrefs = True
    args.include_softfails = True
    args.builds = ":18520:kernel-ec2,:18179:kernel-ec2"
    args.job_group_urls = "https://openqa.suse.de/group_overview/161"
    args.load_dir = Path(__file__).resolve().parent / "broken-softfails"

    report = str(openqa_review.generate_report(args))
    compare_report(report, args.load_dir / "report-broken-softfails.md")


def test_finding_bugrefs_in_softfailures() -> None:
    args = cache_test_args_factory()
    test_browser = Mock()
    result_data = {"job": {"testresults": [{"result": "softfailed", "name": "module-name"}]}}
    test_browser.get_json = MagicMock(return_value=result_data)
    report = openqa_review.ArchReport(
        "x86_64", {"skipped": {}}, args, "root/url", openqa_review.BrowserSet(None, None, test_browser)
    )

    # searching bugrefs in softfails: no bugref in details
    result = {"href": "job/42", "state": "IMPROVED", "bugref": "not assigned"}
    report._search_for_bugrefs_for_softfailures({"some-result": result})
    assert result["bugref"] == "missing/unsupported bug reference", ""
    test_browser.get_json.assert_has_calls([
        call("/api/v1/jobs/42/details"),
        call("job/42/file/details-module-name.json"),
    ])

    # searching bugrefs in softfails: result structure incomplete
    test_browser.get_json = MagicMock(return_value={})
    result["bugref"] = "not assigned"
    report._search_for_bugrefs_for_softfailures({"some-result": result})
    assert result["bugref"] == "not assigned", "incomplete test result skipped, no bugref assigned"
    test_browser.get_json.assert_has_calls([call("/api/v1/jobs/42/details")])


def test_arch_distinguish() -> None:
    args = cache_test_args_factory()
    args.arch = None
    args.job_group_urls = args.host + "/group_overview/4"

    report = str(openqa_review.generate_report(args))
    assert "ppc64le" in report


def test_browser_decode_content() -> None:
    args = cache_test_args_factory()
    args.include_softfails = True
    browser = browser_factory(args)
    url = "http://example.com"
    json = '{"spam": "eggs"}'

    content = browser._decode_content(url, json)
    assert content == json
    content = browser._decode_content(url, json, as_json=True)
    assert "spam" in content

    with pytest.raises(DownloadError) as e:
        browser._decode_content("http://example.com", "", as_json=True)
        assert "Unable to decode JSON" in str(e)


def issue_factory(bugref: str, bugref_href: str, args: Namespace) -> openqa_review.Issue:
    browser = browser_factory(args)
    return openqa_review.Issue(
        bugref, bugref_href, query_issue_status=True, progress_browser=browser, bugzilla_browser=browser
    )


def test_get_bugzilla_issue() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "bugzilla"
    issue = issue_factory("boo#9315715", "https://bugzilla.opensuse.org/show_bug.cgi?id=9315715", args)
    assert str(issue) == "[boo#9315715](https://bugzilla.opensuse.org/show_bug.cgi?id=9315715) (Ticket not found)"

    try:
        issue_factory("boo#9315716", "https://bugzilla.opensuse.org/show_bug.cgi?id=9315716", args)
    except BugzillaError as e:
        assert e.message == "The username or password you entered is not valid."
        assert e.code == 300


def test_bugzilla_with_api_key() -> None:
    openqa_review.config.remove_option("product_issues", "username")
    openqa_review.config.remove_option("product_issues", "password")
    openqa_review.config.set("product_issues", "api_key", "token")
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "bugzilla"
    browser = openqa_review.bugzilla_browser_factory(args)
    assert browser.api_key, "API key used"
    issue = openqa_review.Issue(
        "boo#0815",
        "https://bugzilla.opensuse.org/show_bug.cgi?id=0815",
        query_issue_status=True,
        bugzilla_browser=browser,
        progress_browser=browser,
    )
    assert issue.bugid == 815, "Bugzilla issue parsed"


def test_querying_last_bugzilla_comment() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "bugzilla"
    issue = issue_factory("boo#0815", "https://bugzilla.opensuse.org/show_bug.cgi?id=0815", args)
    (comment_date, comment_text) = issue.last_comment
    assert str(comment_date) == "2021-11-15 00:00:00+00:00", "creation time read"
    assert comment_text == "most recent bugzilla comment", "most recent comment returned"
    assert issue.last_comment_delay == 14, "last comment was added after 14 days"


def test_querying_last_progress_comment() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "progress"
    issue = issue_factory("poo#102440", "https://progress.opensuse.org/issues/102440", args)
    (comment_date, comment_text) = issue.last_comment
    assert str(comment_date) == "2021-11-15 00:00:00+00:00", "last update time read"
    assert comment_text == "latest progress note", "most recent note returned"
    assert issue.last_comment_delay == 7, "last comment was added after 7 days"
    issue = issue_factory("poo#102442", "https://progress.opensuse.org/issues/102442", args)
    assert issue.last_comment_delay == 0, "no delay for only one comment"
    issue = issue_factory("poo#102441", "https://progress.opensuse.org/issues/102441", args)
    assert issue.error, "error flag set for non-existing issue"
    (comment_date, comment_text) = issue.last_comment
    assert comment_date is None, "no comment date returned for non-existing progress issue"
    assert comment_text is None, "no comment text returned for non-existing progress issue"


def test_querying_last_comment_of_unknown_bugrefs() -> None:
    args = cache_test_args_factory()
    args.load_dir = Path(__file__).resolve().parent / "bugzilla"
    issue = issue_factory("b0o#9315715", "https://bugzilla.opensuse.org/show_bug.cgi?id=9315715", args)
    (comment_date, comment_text) = issue.last_comment
    assert comment_date is None, "no comment date returned for unsupported issue"
    assert comment_text is None, "no comment text returned for unsupported issue"


def test_reopening_progress_issue(mocker: MockerFixture) -> None:
    browser_mock = mocker.patch.object(Browser, "json_rest")
    args = cache_test_args_factory()
    issue = issue_factory("poo#102440", "https://progress.opensuse.org/issues/102440", args)
    issue.status = "Resolved"
    issue.reopen("Test note")
    issue.reopen()  # with default note
    issue.status = "workable"
    issue.reopen("Test note 2")
    browser_mock.assert_called()
    call_name, call_args, call_kwargs = browser_mock.mock_calls[0]
    assert call_args[0] == "https://progress.opensuse.org/issues/102440.json", "URL"
    assert call_args[1] == "PUT", "method"
    assert call_args[2] == {"issue": {"status_id": 4, "notes": "Test note"}}, "data"
    call_name, call_args, call_kwargs = browser_mock.mock_calls[1]
    assert call_args[0] == "https://progress.opensuse.org/issues/102440.json", "URL (call with default note)"
    assert call_args[1] == "PUT", "method (call with default note)"
    assert call_args[2] is not None, "data present (call with default note)"
    call_name, call_args, call_kwargs = browser_mock.mock_calls[2]
    assert call_args[0] == "https://progress.opensuse.org/issues/102440.json", "URL (call for workable ticket)"
    assert call_args[1] == "PUT", "method (call for workable ticket)"
    assert call_args[2] == {"issue": {"notes": "Test note 2"}}, "data (no status for workable ticket)"


def test_reopening_bugzilla_ticket(mocker: MockerFixture) -> None:
    browser_mock_rpc = mocker.patch.object(Browser, "json_rpc_post")
    args = cache_test_args_factory()
    issue = issue_factory("boo#0815", "https://bugzilla.opensuse.org/show_bug.cgi?id=0815", args)
    issue.status = "RESOLVEd"
    issue.reopen("Test note")
    issue.status = "CONFIRMED"
    issue.reopen("Test note 2")
    browser_mock_rpc.assert_called()
    call_name, call_args, call_kwargs = browser_mock_rpc.mock_calls[0]
    expected_data = {"ids": [815], "status": "REOPENED", "comment": {"body": "Test note", "is_private": False}}
    assert call_args[0] == "/jsonrpc.cgi", "URL"
    assert call_args[1] == "Bug.update", "method"
    assert call_args[2] == expected_data, "data"
    call_name, call_args, call_kwargs = browser_mock_rpc.mock_calls[1]
    del expected_data["status"]
    expected_data = {"id": 815, "comment": "Test note 2", "is_private": False}
    assert call_args[0] == "/jsonrpc.cgi", "URL for just leaving note on unresolved ticket"
    assert call_args[1] == "Bug.add_comment", "method for just leaving note on unresolved ticket"
    assert call_args[2] == expected_data, "data for just leaving note on unresolved ticket"
