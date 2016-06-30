#!/usr/bin/env python

"""
TumbleSLE release script.

Based on test results as available on an openQA instance this script can check
and compare builds. The basic idea is to release a new version of a product,
e.g.  a 'SLE development build' as the new version of TumbleSLE if it is as good
or better than the previous TumbleSLE release. Supports whitelisting known and
accepted failures comparable to what Tumbleweed does. The whitelist can be
stored in a config file or as command line parameters. It is suggested to try
out what the script would do using the '--dry-run' and/or the '--dry-run-rsync'
parameters. Call '--help' for more help on all available parameters

The script is expected to be executed on the host on where the TumbleSLE target
directory structure is available on. The source, i.e. where to copy assets from,
can be remote and the path can be specified in an rsync-compatible way, e.g.
"openqa:/var/lib/openqa/factory/"
"""

# Python 2 and 3: easiest option
# see http://python-future.org/compatible_idioms.html
from future.standard_library import install_aliases  # isort:skip to keep 'install_aliases()'
install_aliases()
from future.utils import iteritems

import argparse
import fnmatch
import glob
import logging
import os.path
import re
import sys
import time
from collections import defaultdict
from configparser import ConfigParser
from subprocess import check_call

import yaml

try:
    from openqa_review import Browser, add_load_save_args
except ImportError:
    # why is this necessary from py.test? crosscheck if it works if called from tox
    from openqa_review.openqa_review import Browser, add_load_save_args

logging.basicConfig()
log = logging.getLogger(sys.argv[0] if __name__ == "__main__" else __name__)


CONFIG_PATH = os.path.expanduser('~') + '/.tumblesle_releaserc'
CONFIG_USAGE = """
You are missing configuration file with the proper format.
Example:
[Leap 42.2]
# comma separated list of scenarios or test_suites
# see https://progress.opensuse.org/projects/openqav3/wiki/Wiki#Glossary for definitions
# example scenario: openSUSE-Tumbleweed-DVD-x86_64-gnome@64bit
whitelist = arm7l-foo,bar@uefi

"""


def scenario(job):
    s = job['settings']
    return '-'.join([s['DISTRI'], s['VERSION'], s['FLAVOR'], s['ARCH'], s['TEST']]) + '@' + s['MACHINE']


class UnsupportedRsyncArgsError(Exception):

    """Unsupported rsync arguments where used."""

    pass


class TumblesleRelease(object):

    """Check for releasable builds and release them as TumbleSLE if they are at least as good as the current one."""

    def __init__(self, args):
        """Construct object and save forwarded arguments."""
        verbose_to_log = {
            0: logging.CRITICAL,
            1: logging.ERROR,
            2: logging.WARN,
            3: logging.INFO,
            4: logging.DEBUG
        }
        logging_level = logging.DEBUG if args.verbose > 4 else verbose_to_log[args.verbose]
        log.setLevel(logging_level)
        log.debug("args: %s" % args)
        self.args = args
        config = ConfigParser()
        config_entries = config.read(self.args.config_path)
        self.whitelist = [i.strip() for i in args.whitelist.split(',')]
        if config_entries:
            self.whitelist += [i.strip() for i in config.get(self.args.product, 'whitelist').split(',')]
        else:
            log.info("No configuration file '{}' for whitelist, only using optionally specified command line whitelist".format(self.args.config_path))
            log.debug(CONFIG_USAGE)
        # does not look so nice, can be improved. Removing empty string entries.
        self.whitelist = [i for i in self.whitelist if i]
        log.info("Whitelist content for %s: %s" % (self.args.product, self.whitelist))
        self.browser = Browser(args, args.openqa_host)

    def run(self, do_run=True):
        """Continously run while 'do_run' is True, check for last build and release if satisfying."""
        while do_run:
            if self.args.run_once:
                log.debug("Requested to run only once")
                do_run = False
            self.one_run()
            time.sleep(self.args.sleeptime)
        log.debug("Stopping")

    def one_run(self):
        """Like run but only one run, not continuous execution."""
        self.check_last_builds()
        if self.release_build is None:
            return
        self.release()

    def retrieve_server_isos(self):
        """Retrieve name of ISOS for matching pattern from openQA host."""
        match_re = fnmatch.translate(self.args.match)

        def is_matching_iso(i):
            return 'iso' in i['type'] and 'Staging' not in i['name'] and re.match(match_re, i['name'])
        log.debug("Finding most recent ISO matching regex '%s'" % match_re)
        assets = self.browser.get_json('/api/v1/assets')['assets']
        isos = [i['name'] for i in assets if is_matching_iso(i)]
        return isos

    def retrieve_jobs_by_result(self, build):
        """Retrieve jobs for current group by build id, returns dict with result as keys."""
        group_id = int(self.args.group_id)
        log.debug("Getting jobs in build %s ..." % build)
        jobs_build = self.browser.get_json('/api/v1/jobs?state=done&build=%s&group_id=%s' % (build, group_id))['jobs']
        jobs_in_build_product = [i for i in jobs_build if i['group_id'] == group_id]
        # sorting list by job id then create dict and just keep most recent job in each scenario
        jobs_in_build_product.sort(key=lambda j: j['id'], reverse=True)
        jobs_by_scenario = {scenario(j): j for j in jobs_in_build_product}
        # TODO this can be improved, first converting list to dict, then back to list in dict argument
        jobs_by_result = defaultdict(list)
        for k, v in iteritems(jobs_by_scenario):
            # discarding scenario key. Would be nicer to preserve it
            jobs_by_result[v['result']].append(v)
        return jobs_by_result

    def _filter_whitelisted_fails(self, failed_jobs):
        def whitelisted(job):
            for entry in self.whitelist:
                if entry in scenario(job):
                    log.debug("Found whitelist failed job %s because it matches %s" % (job['name'], entry))
                    return True
            return False
        failed_jobs_without_whitelisted = [job for job in failed_jobs if not whitelisted(job)]
        return failed_jobs_without_whitelisted

    def check_last_builds(self):
        """Check last builds and return releasable build(s)."""
        self.release_build = None
        log.debug("Checking last builds on %s ..." % self.args.openqa_host)
        isos = self.retrieve_server_isos()
        last_iso = sorted(isos)[-1]
        log.debug("Found last ISO %s" % last_iso)
        build = {}
        # TODO check for running build. It should have the same effect as we compare nr of passed anyway later but it's better to explictly abort faster
        build['last'] = re.search('(?<=-Build)[0-9@]+', last_iso).group() if self.args.check_build is 'last' else self.args.check_build
        log.debug("Found last build %s" % build['last'])
        jobs_by_result = {}
        jobs_by_result['last'] = self.retrieve_jobs_by_result(build['last'])
        passed, failed = {}, {}
        passed['last'] = len(jobs_by_result['last']['passed'])
        failed['last'] = len(jobs_by_result['last']['failed'])
        log.info('Most recent build %s: passed: %s, failed: %s' % (build['last'], passed['last'], failed['last']))

        # IF NOT last_stored_finish_build
        #    read tumblesle repo, find last tumblesle build
        #    last_stored_finish_build = last tumblesle build aka. "released"
        #
        if self.args.check_against_build == 'tagged':
            raise NotImplementedError("tag check not implemented")
        elif self.args.check_against_build == 'release_info':
            self.release_info_path = os.path.join(self.args.dest, self.args.release_file)
            with open(self.release_info_path, 'r') as release_info_file:
                release_info = yaml.load(release_info_file)
                build['released'] = release_info[self.args.product]['build']
        else:
            build['released'] = self.args.check_against_build
        # IF NOT finished build newer than last_stored_finished_build
        #    continue wait
        #
        if build['last'] <= build['released']:
            log.info("Specified last build {last} is not newer than released {released}, skipping".format(**build))
            return
        log.debug("Retrieving results for released build %s" % build['released'])
        jobs_by_result['released'] = self.retrieve_jobs_by_result(build['released'])
        # read whitelist from tumblesle
        # TODO whitelist could contain either bugs or scenarios while I prefer bugrefs :-)
        hard_failed_jobs = {k: self._filter_whitelisted_fails(jobs_by_result[k]['failed']) for k in ['released', 'last']}
        # count passed, failed for both released/new
        passed['released'] = len(jobs_by_result['released']['passed'])
        hard_failed = {k: len(v) for k, v in iteritems(hard_failed_jobs)}
        whitelisted = {'last': failed['last'] - hard_failed['last']}
        passed['last'] += whitelisted['last']
        assert (passed['last'] + hard_failed['last']) > 0, "passed['last'] (%s) + hard_failed['last'] (%s) must be more than zero" % (
            passed['last'], hard_failed['last'])
        assert (passed['released'] + hard_failed['released']) > 0
        log.debug('%s: %s/%s vs. %s: %s/%s' % (build['last'], passed['last'], hard_failed['last'],
                                               build['released'], passed['released'], hard_failed['released']))
        if passed['last'] >= passed['released'] and hard_failed['last'] <= hard_failed['released']:
            log.info("Found new good build %s" % build['last'])
            self.release_build = build['last']
            # TODO auto-remove entries from whitelist which are passed now
        else:
            hard_failed_jobs_by_scenario = {k: {scenario(j): j for j in v} for k, v in iteritems(hard_failed_jobs)}
            sets = {k: set(v) for k, v in iteritems(hard_failed_jobs_by_scenario)}
            new_failures = sets['last'].difference(sets['released'])
            new_fixed = sets['released'].difference(sets['last'])
            log.info("Regression in new build %s, new failures: %s" % (build['last'], ', '.join(new_failures)))
            log.debug("new fixed: %s" % ', '.join(new_fixed))

        # # assuming every job in released_failed is in whitelist
        # if len(hard_failed) > previous_hard_failed:
        #     return skip_release (cause: product regression) -> notify on new blockers
        # if len(new_passed < released_passed):
        #     return skip_release (cause: test coverage regression) -> notify stats, e.g. which scenario missing

    def release(self):
        """Release new version of TumbleSLE by syncing from openQA instance to TumbleSLE server."""
        log.debug("Releasing new TumbleSLE: Build %s" % self.release_build)
        # # do release
        # TODO in openQA as soon as there is comment access over API:
        #   - tag new build
        #   - remove last tag (or update)
        #
        # sync repo/iso/hdd to pre_release on tumblesle archive
        rsync_opts = ['-aHP']
        # rsync supports a dry-run option so we can also select a dry-run there. This only works if the directory structure exists
        if self.args.dry_run_rsync:
            rsync_opts += ['--dry-run']

        if not self.args.src.endswith('/') or not self.args.dest.endswith('/'):
            raise UnsupportedRsyncArgsError()
        build_dest = os.path.join(self.args.dest, self.release_build) + '/'
        rsync_opts += ["--include=**/%s%s*" % (self.args.match, self.release_build)]
        if self.args.match_hdds:
            rsync_opts += ["--include=**/%s%s*" % (self.args.match_hdds, self.release_build)]
        rsync_opts += ["--include=iso/", "--include=hdd/", "--exclude=*"]
        cmd = ["rsync"] + rsync_opts + [self.args.src, build_dest]
        log.debug("Calling '%s'" % ' '.join(cmd))
        if not self.args.dry_run or self.args.dry_run_rsync:
            check_call(cmd)
        log.debug("Updating symlinks within %s/ for each asset (Build%s->current)" % (self.release_build, self.release_build))
        for i in glob.glob(build_dest + '*/*'):
            tgt = os.path.join(os.path.dirname(i), os.path.basename(i).replace(self.release_build, 'CURRENT'))
            if not os.path.exists(tgt):
                os.symlink(i, tgt)
        log.debug("Updating folder symlinks %s/ -> release/" % self.release_build)
        release_tgt = os.path.join(self.args.dest, 'release')
        if self.args.dry_run:
            log.info("Would symlink %s -> %s" % (build_dest, release_tgt))
        else:
            if os.path.exists(release_tgt):
                os.remove(release_tgt)
            os.symlink(self.release_build, release_tgt)
        log.debug("Release DONE")
        # This could be a place where to send further notifications


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-v', '--verbose',
                        help="Increase verbosity level, specify multiple times to increase verbosity",
                        action='count', default=1)
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help="Only do read-only or simulate actions, does not release TumbleSLE")
    parser.add_argument('--dry-run-rsync', action='store_true',
                        help="Execute rsync with dry-run. Should be specified additionally to '--dry-run'")
    parser.add_argument('--openqa-host',
                        help="openQA host to retrieve results from",
                        default='https://openqa.opensuse.org')
    parser.add_argument('--group-id',
                        help="Group id to search in from openQA host",
                        default=19)
    parser.add_argument('--product',
                        help="The product name to act upon, must be equivalent to --group-id and must match entry in config file (if any).",
                        default="Leap 42.2")
    parser.add_argument('--check-build',
                        help="""If specified, checks specified build number (integer) instead of 'last' finished.""",
                        default='last')
    parser.add_argument('--check-against-build',
                        help="""If specified, checks against specified build number (integer).
                        Specify 'release_info' for reading release info file from destination folder, see '--release-file' and '--dest'.
                        Specify 'tagged' for last tagged on group overview page within openQA""",
                        default='release_info')
    parser.add_argument('--run-once', action='store_true',
                        help="Only run once, not continuously")
    parser.add_argument('--config-path',
                        help="Path to config file with whitelist.",
                        default=CONFIG_PATH)
    parser.add_argument('--whitelist',
                        help="Whitelist entries as for the config file (comma separated). Additional to config file entries",
                        default='')
    parser.add_argument('--src',
                        help="""Source directory for rsync call pointing to factory subdir within openQA.
                        Make sure to end the path with '/'. Can be anything rsync understands""",
                        default='/var/lib/openqa/factory/')
    parser.add_argument('--dest',
                        help="""Target directory for rsync call where to put TumbleSLE assets. Make sure to end the path with '/'.
                        Can be anything rsync understands but must be local.""",
                        default='/srv/www/tumblesle/')
    parser.add_argument('--match',
                        help="Globbing pattern that has to be matched when searching for builds as well as when syncing assets on release",
                        default='open*-42.2*x86_64*')
    parser.add_argument('--match-hdds',
                        help="Additional globbing pattern to '--match' for hdd images as they are named differently more often than not",
                        default=None)
    parser.add_argument('--release-file',
                        help="""Name of release file including the build number. This file is read from the path specified by '--dest'
                        and is written back to it.""",
                        default='.release_info')
    parser.add_argument('--sleeptime',
                        help="Time to sleep between runs in seconds. Has no effect with '--run-once'",
                        default=240)
    add_load_save_args(parser)
    return parser.parse_args()


def main():  # pragma: no cover, only interactive
    args = parse_args()
    tr = TumblesleRelease(args)
    tr.run()


if __name__ == "__main__":
    main()
