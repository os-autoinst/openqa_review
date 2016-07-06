"""
tests for openqa_review.

Can't get isort to work on this file

isort:skip_file
"""

# see http://python-future.org/compatible_idioms.html
from future.standard_library import install_aliases  # isort:skip to keep 'install_aliases()'

install_aliases()
import contextlib
import os.path
import re
import shutil
import sys
import tempfile
from argparse import Namespace
from urllib.parse import urljoin, urlparse

import pytest

from openqa_review import openqa_review  # SUT


def args_factory():
    args = Namespace()
    args.host = 'https://openqa.opensuse.org'
    args.job_group_urls = None
    args.job_groups = None
    args.no_progress = True
    args.verbose = 1
    args.output_state_results = False
    args.base_url = '/'
    args.verbose_test = 4
    args.arch = 'x86_64'
    args.save = False
    args.load = False
    args.load_dir = '.'
    args.builds = None
    args.against_reviewed = None
    args.running_threshold = 0
    return args


# similar to python3.2 TemporaryDirectory, not available on older versions
# also see http://stackoverflow.com/a/13379969/5031322

@contextlib.contextmanager
def TemporaryDirectory():  # noqa
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_doctest():
    import doctest
    import openqa_review
    # TODO this should have tested e.g. line 'return unquote...' in filename_to_url but coverage report does not show it
    assert doctest.testmod(openqa_review, raise_on_error=True)


def test_help():
    sys.argv += '--help'.split()
    with pytest.raises(SystemExit):
        openqa_review.main()


def cache_test_args_factory():
    args = args_factory()
    args.job_group_urls = args.host + '/group_overview/25'
    args.load = True
    args.load_dir = os.path.dirname(os.path.realpath(__file__))
    return args


def compare_report(report, ref_report):
    # for simpler display of the diff in case of differences it helps to have
    # both reports in same encoding, i.e. casting to str
    lines = str(report).splitlines()
    ref = ref_report.splitlines()
    # report equals the reference except for the time tag so skip the
    # date/time line
    del lines[3], ref[3]
    assert lines == ref


def test_previously_loaded_cache_file_is_generated_into_valid_verbose_report_if_configured():
    args = cache_test_args_factory()
    report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report
    # Missing architecture is reported
    assert re.search("Missing arch.*i586", report)
    ref_report = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'report25_TTT.md')).read()
    compare_report(report, ref_report)


def test_previously_loaded_cache_file_is_generated_into_valid_terse_report_by_default():
    args = cache_test_args_factory()
    args.verbose_test = 1
    report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report
    ref_report = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'report25_terse.md')).read()
    compare_report(report, ref_report)


def test_previously_loaded_cache_file_is_generated_into_ref_report_l2():
    args = cache_test_args_factory()
    args.verbose_test = 2
    report = openqa_review.generate_report(args)
    ref_report = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'report25_T.md')).read()
    compare_report(report, ref_report)


def test_previously_loaded_cache_file_is_generated_into_ref_report_l3():
    args = cache_test_args_factory()
    args.verbose_test = 3
    report = openqa_review.generate_report(args)
    ref_report = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'report25_TT.md')).read()
    compare_report(report, ref_report)


def test_builds_can_be_specified_and_appear_in_report():
    args = cache_test_args_factory()
    args.builds = '0313,0308'
    report = openqa_review.generate_report(args)
    assert '**Build:** {} (reference {})'.format(*args.builds.split(',')) in report


def test_too_high_verbosity_selection_yields_still_valid_selection():
    args = cache_test_args_factory()
    args.verbose_test = 5
    report = openqa_review.generate_report(args)
    assert report != ''


def test_ha_tests_yields_valid_report_with_valid_build_nr():
    args = cache_test_args_factory()
    args.arch = None  # let this test check architectures by itself to reach good test coverage
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'live')
    args.job_group_urls = args.host + '/group_overview/27'
    report = openqa_review.generate_report(args)
    assert '0104@0351' in report


def test_specified_job_group_yields_single_product_report():
    args = cache_test_args_factory()
    args.job_group_urls = None
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'single_job_group')
    args.job_groups = 'openSUSE Tumbleweed  1.Gnome'
    report = openqa_review.generate_report(args)
    assert args.job_groups in report
    # There must be only one job group tag
    assert len([l for l in report.splitlines() if l.startswith('#')]) == 1

    # Invalid name should yield assertion with helpful message
    args.job_groups = 'openSUSE Tumbleweed FOO'
    with pytest.raises(AssertionError) as e:
        report = openqa_review.generate_report(args)
    assert 'No job group' in str(e.value)

    # Multiple job groups can be specified
    args.job_groups = 'openSUSE Tumbleweed  1.Gnome,openSUSE Tumbleweed  2.KDE'
    # we don't actually need to check the parsing just make sure
    # openqa_review tries to parse all and as there is no cache page
    # for 'openSUSE Tumbleweed  2.KDE' saved, we assume its corresponding
    # page can not be retrieved.
    # Unfortunately we can not easily be more specific about the
    # exception as python2 raises IOError, python3 FileNotFoundError
    # but we can check the content anyway.
    with pytest.raises(Exception) as e:
        report = openqa_review.generate_report(args)
    assert 'group_overview:26' in str(e.value)

    # job groups can also be used as an incomplete search tags or regex
    args.job_groups = '(Gnome|KDE)'
    # To increase statement and branch coverage we enable progress report here.
    # It will be invisible but executed.
    args.no_progress = False
    # see above
    with pytest.raises(Exception) as e:
        report = openqa_review.generate_report(args)
    assert 'group_overview:26' in str(e.value)


def test_get_build_urls_to_compare_finds_last_reviewed_if_selected():
    args = cache_test_args_factory()
    browser = openqa_review.Browser(args, urljoin(args.host, args.base_url))
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='0311')
    assert '=0311' in current
    assert '=0307' in reviewed

    # If '--against-reviewed' is 'last', search for the latest finished
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='last')
    assert '=0313' in current
    assert '=0307' in reviewed

    # Also accept still running if threshold is increased
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='last', running_threshold=45)
    assert '=0318' in current
    assert '=0307' in reviewed

    # Not accepted if slightly below threshold
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='last', running_threshold=36)
    assert '=0313' in current
    assert '=0307' in reviewed


def test_non_number_build_nr_also_finds_valid_review_build_urls():
    args = cache_test_args_factory()
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'live')
    args.job_group_urls = args.host + '/group_overview/27'
    browser = openqa_review.Browser(args, urljoin(args.host, args.base_url))
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='last')
    assert '=0104%400351' in current  # i.e. escaped '0104@0351'
    assert '=0097%400305' in reviewed

    # if no review comments are found we revert to the last two finished
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'live_no_review')
    browser = openqa_review.Browser(args, urljoin(args.host, args.base_url))
    current, reviewed = openqa_review.get_build_urls_to_compare(browser, args.job_group_urls, against_reviewed='last')
    assert '=0104%400351' in current  # i.e. escaped '0104@0351'
    assert '=0104%400350' in reviewed  # no review comments found, reverting to last two finished


def test_generate_report_with_progress_notification_does_not_fail():
    args = cache_test_args_factory()
    # Not easy to test automatically but at least we can call it and assume it also gives valid results
    args.no_progress = False
    args.job_groups_url = None
    report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report


def test_state_report_does_not_break_generation():
    args = cache_test_args_factory()
    args.output_state_results = True
    report = openqa_review.generate_report(args)
    assert report


def test_get_job_groups_yields_job_groups_in_page():
    args = cache_test_args_factory()
    args.job_groups = None
    args.job_group_urls = None
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'single_job_group')
    root_url = urljoin(args.host, args.base_url)
    browser = openqa_review.Browser(args, root_url)
    job_groups = openqa_review.get_job_groups(browser, root_url, args)
    assert len(job_groups.keys()) == 8


# TODO should be covered by doctest already but I can not get coverage analysis to work with doctests in py.test
def test_filename_to_url_encodes_valid_url():
    url_object = urlparse(openqa_review.filename_to_url('https%3A::openqa.opensuse.org:group_overview:25'))
    assert url_object.scheme == 'https'
    assert url_object.netloc == 'openqa.opensuse.org'


def test_single_job_group_pages_can_be_cached_from_cache():
    args = cache_test_args_factory()
    with TemporaryDirectory() as tmp_dir:
        args.save_dir = tmp_dir
        args.save = True
        report = openqa_review.generate_report(args)
        assert '**Common issues:**' in report


def test_new_tests_appearing_in_builds_are_supported():
    args = cache_test_args_factory()
    args.job_groups = None
    args.builds = '0405,0389'
    args.arch = 'i586'
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'differing_tests')
    report = openqa_review.generate_report(args)
    # There should be one new test which is failing and has not been there in before
    assert '* ***btrfs@zkvm***: https://openqa.opensuse.org/tests/181148 (reference NONE )' in report


@pytest.mark.webtest
def test_default_returns_valid_markdown_document():
    args = args_factory()
    report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report


@pytest.mark.webtest
def test_single_job_group_with_extended_test_output_returns_valid_markdown_document():
    args = args_factory()
    args.job_group_urls = args.host + '/group_overview/25'
    report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report


@pytest.mark.webtest
def test_single_job_group_pages_can_be_cached_from_web():
    args = args_factory()
    args.job_group_urls = args.host + '/group_overview/25'

    with TemporaryDirectory() as tmp_dir:
        args.save_dir = tmp_dir
        report = openqa_review.generate_report(args)
    assert '**Common issues:**' in report
