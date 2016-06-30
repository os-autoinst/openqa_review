# see http://python-future.org/compatible_idioms.html
from future.standard_library import install_aliases  # isort:skip to keep 'install_aliases()'

install_aliases()
import contextlib
import os
import os.path
import shutil
import sys
import tempfile
from argparse import Namespace

import pytest
import yaml
from openqa_review import tumblesle_release  # SUT
from openqa_review.tumblesle_release import UnsupportedRsyncArgsError


# similar to python3.2 TemporaryDirectory, not available on older versions
# also see http://stackoverflow.com/a/13379969/5031322


@contextlib.contextmanager
def TemporaryDirectory():  # noqa
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@contextlib.contextmanager
def TumblesleDirectory(args):  # noqa
    with TemporaryDirectory() as tmp_dir:
        args.src = os.path.join(tmp_dir, 'src') + '/'
        args.dest = os.path.join(tmp_dir, 'dest') + '/'
        # create a fake config entry
        args.config_path = os.path.join(tmp_dir, 'config_file')
        with open(args.config_path, 'w') as config:
            config.write("""[Leap 42.2]
whitelist = arm7l-foo,bar@uefi""")

        # create some fake entries
        os.mkdir(args.src)
        for d in ['iso', 'hdd', 'dest']:
            os.mkdir(os.path.join(args.src, d))
        isos = ['iso/openSUSE-Leap-42.2-DVD-x86_64-Build0056-Media.iso', 'iso/openSUSE-Leap-42.2-NET-x86_64-Build0052-Media.iso']
        hdds = ['hdd/opensuse-Tumbleweed-aarch64-20160626-gnome@aarch64.qcow2', 'hdd/opensuse-42.2-x86_64-0056-gnome@64bit.qcow2']
        for asset in isos + hdds:
            open(os.path.join(args.src, asset), 'w').close()
        # The destination folder must exist
        os.mkdir(args.dest)
        yield tmp_dir


@pytest.fixture
def args():
    args = Namespace()
    args.verbose = 5
    args.dry_run = True
    args.dry_run_rsync = False
    args.config_path = '/tmp/this/file/does/not/exist'
    args.openqa_host = 'https://openqa.opensuse.org'
    args.product = 'Leap 42.2'
    args.group_id = 19
    args.check_against_build = '0046'
    args.whitelist = ''
    args.match = 'open*-42.2*x86_64*'
    args.check_build = 'last'
    args.run_once = True
    args.release_file = '.release_info'
    args.sleeptime = 0
    args.load = True
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tumblesle/0046_0056_new_release')
    # Enable saving and disable loading if you want to add new test data downloaded from hosts
    #  args.save = True
    #  args.save_dir = args.load_dir
    return args


def test_help():
    sys.argv += '--help'.split()
    with pytest.raises(SystemExit):
        tumblesle_release.main()


def test_compare_old_bad_against_new_good_yields_release(args):
    with TumblesleDirectory(args):
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == '0056'
        # same again, this time with rsync dry-run
        args.dry_run_rsync = True
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == '0056'
        # same again, this times 'hot'
        args.dry_run = False
        args.dry_run_rsync = False
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == '0056'
        # subsequent call with same build has same effect
        tr = tumblesle_release.TumblesleRelease(args)
        tr.one_run()
        assert tr.release_build == '0056'


def test_specifying_more_recent_check_build_does_not_yield_release(args):
    args.check_against_build = '0056'
    tr = tumblesle_release.TumblesleRelease(args)
    tr.one_run()
    assert tr.release_build is None


def test_compare_old_better_against_new_good_yields_regression(args):
    args.check_against_build = '0052'
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tumblesle/0052_0056_regression')
    args.run_once = True
    tr = tumblesle_release.TumblesleRelease(args)
    tr.run()
    assert tr.release_build is None


def test_old_better_against_new_good_plus_whitelist_yields_forced_release(args):
    args.check_against_build = '0052'
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tumblesle/0052_0056_regression')
    args.whitelist = 'lxde@Laptop_64, DVD-x86_64-gnome@64bit, opensuse-42.2-NET-x86_64-gnome@64bit, \
            cryptlvm-image@uefi, gnome@Laptop_64, \
            sysauth_gnome@64bit, opensuse-42.2-NET-x86_64-RAID1@64bit'
    tr = tumblesle_release.TumblesleRelease(args)
    tr.check_last_builds()
    assert tr.release_build == '0056'


def test_select_different_build_checks_specified(args):
    args.check_build = '0051'
    args.check_against_build = '0047'
    args.load_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tumblesle/0047_0051_explicit_no_release')
    tr = tumblesle_release.TumblesleRelease(args)
    tr.check_last_builds()
    assert tr.release_build is None


def test_tagged_not_yet_implemented(args):
    args.run_once = False
    args.check_against_build = 'tagged'
    with pytest.raises(NotImplementedError):
        tumblesle_release.TumblesleRelease(args).run()


def test_unsafe_rsync_args_are_catched(args):
    args.src = '/tmp/foo'
    with pytest.raises(UnsupportedRsyncArgsError):
        tumblesle_release.TumblesleRelease(args).run()


def test_compare_old_released_with_release_info_against_new_good_yields_release(args):
    args.check_against_build = 'release_info'
    with TumblesleDirectory(args):
        with open(os.path.join(args.dest, '.release_info'), 'w') as release_info:
            yaml.dump({args.product: {'build': '0046'}}, release_info)
            tr = tumblesle_release.TumblesleRelease(args)
            tr.one_run()
            assert tr.release_build == '0056'
