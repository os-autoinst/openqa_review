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

Notifications over AMQP are sent out if a host has been configured
appropriately in the configuration file (see config file example). The
notifications are serialized in JSON strings.
"""

# Python 2 and 3: easiest option
# see http://python-future.org/compatible_idioms.html
from __future__ import absolute_import
from future.standard_library import install_aliases  # isort:skip to keep 'install_aliases()'
install_aliases()
from future.utils import iteritems

import argparse
import fnmatch
import glob
import logging
import json
import os.path
import pika
import re
import sys
import time
from collections import defaultdict, deque
from configparser import ConfigParser
from subprocess import check_call

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from openqa_review.browser import Browser, add_load_save_args

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

#[notification]
#host = localhost
#username = guest
#password = guest
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
        self.release_info_path = os.path.join(self.args.dest, self.args.release_file)
        self.browser = Browser(args, args.openqa_host)
        if not config.has_section('notification'):
            return
        self.credentials = pika.PlainCredentials(config.get('notification', 'username', fallback='guest'),
                                                 config.get('notification', 'password', fallback='guest'))
        self.notify_host = config.get('notification', 'host', fallback='kazhua.suse.de')
        self.notify_connect()

    def notify_connect(self):
        """Connect to notification bus."""
        self.notify_connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.notify_host, credentials=self.credentials, heartbeat_interval=10))
        self.notify_channel = self.notify_connection.channel()
        self.notify_channel.exchange_declare(exchange='pubsub', type='topic', passive=True, durable=True)
        self.notify_topic = 'suse.tumblesle'
        self.notify_seen = deque(maxlen=self.args.seen_maxlen)

    def __del__(self):
        """Cleanup notification objects."""
        if not hasattr(self, 'notify_connection'):
            return
        self.notify_connection.close()

    def notify(self, message, topic='info'):
        """Send notification over messaging bus."""
        if not hasattr(self, 'notify_channel'):
            log.debug("No notification channel enabled, discarding notify.")
            return
        body = json.dumps(message)
        if body in self.notify_seen:
            log.debug("notification message already sent out recently, not resending: %s" % body)
            return
        tries = 7  # arbitrary
        for t in range(tries):
            try:
                self.notify_channel.basic_publish(exchange='pubsub', routing_key='.'.join([self.notify_topic, topic]), body=body)
                break
            except pika.exceptions.ConnectionClosed as e:  # pragma: no cover
                log.warn('sending notification did not work: %s. Retrying try %s out of %s' % (e, t, tries))
                self.notify_connect()
        else:  # pragma: no cover
            log.error('could not send out notification for %s tries, aborting.' % tries)
            raise pika.exceptions.ConnectionClosed()
        self.notify_seen.append(body)

    def run(self, do_run=True):
        """Continously run while 'do_run' is True, check for last build and release if satisfying."""
        while do_run:
            if self.args.run_once:
                log.debug("Requested to run only once")
                do_run = False
            self.one_run()
            if not self.args.run_once:  # pragma: no cover
                log.debug("Waiting for new check %s seconds" % self.args.sleeptime)
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
        assets = self.browser.get_json('/api/v1/assets', cache=self.args.load)['assets']
        isos = [i['name'] for i in assets if is_matching_iso(i)]
        return isos

    def retrieve_jobs_by_result(self, build):
        """Retrieve jobs for current group by build id, returns dict with result as keys."""
        group_id = int(self.args.group_id)
        log.debug("Getting jobs in build %s ..." % build)
        jobs_build = self.browser.get_json('/api/v1/jobs?state=done&latest=1&build=%s&group_id=%s' % (build, group_id), cache=self.args.load)['jobs']
        jobs_in_build_product = [i for i in jobs_build if i['group_id'] == group_id]
        jobs_by_result = defaultdict(list)
        for job in jobs_in_build_product:
            jobs_by_result[job['result']].append(job)
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
        failed['last'] = len(jobs_by_result['last']['failed']) + len(jobs_by_result['last']['softfailed'])
        log.info('Most recent build %s: passed: %s, failed: %s' % (build['last'], passed['last'], failed['last']))

        # IF NOT last_stored_finish_build
        #    read tumblesle repo, find last tumblesle build
        #    last_stored_finish_build = last tumblesle build aka. "released"
        #
        if self.args.check_against_build == 'tagged':
            raise NotImplementedError("tag check not implemented")
        elif self.args.check_against_build == 'release_info':
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
        passed['released'] = len(jobs_by_result['released']['passed']) + len(jobs_by_result['released']['softfailed'])
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
            self.notify({'build': build['last'], 'new_failures': list(new_failures)}, topic='regression')

        # # assuming every job in released_failed is in whitelist
        # if len(hard_failed) > previous_hard_failed:
        #     return skip_release (cause: product regression) -> notify on new blockers
        # if len(new_passed < released_passed):
        #     return skip_release (cause: test coverage regression) -> notify stats, e.g. which scenario missing

    def sync(self, build_dest):
        """Sync repo/iso/hdd to pre_release on tumblesle archive."""
        rsync_opts = ['-aHP']
        # rsync supports a dry-run option so we can also select a dry-run there. This only works if the directory structure exists
        if self.args.dry_run_rsync:
            rsync_opts += ['--dry-run']

        if not self.args.src.endswith('/') or not self.args.dest.endswith('/'):
            raise UnsupportedRsyncArgsError()
        rsync_opts += ["--include=**/%s%s*" % (self.args.match, self.release_build)]
        if self.args.match_hdds:
            rsync_opts += ["--include=**/%s%s*" % (self.args.match_hdds, self.release_build)]
        rsync_opts += ["--include=iso/", "--include=hdd/", "--include=repo/"]
        rsync_opts += ["--filter=+ repo/%s%s*/**" % (self.args.match, self.release_build)]
        rsync_opts += ["--exclude=*"]
        cmd = ["rsync"] + rsync_opts + [self.args.src, build_dest]
        log.debug("Calling '%s'" % ' '.join(cmd))
        if not self.args.dry_run or self.args.dry_run_rsync:
            check_call(cmd)

    def update_release_info(self):
        """Update release info file on destination."""
        log.debug("Updating release_info file")
        release_info = {self.args.product: {'build': self.release_build}}
        release_info_dump = yaml.safe_dump(release_info)
        log.debug("New release info as yaml: %s" % release_info_dump)
        if not self.args.dry_run:
            open(self.release_info_path, 'w').write(release_info_dump)

    def update_symlinks(self, build_dest):
        """Update symlinks to 'current' and 'release' on destination."""
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

    def release(self):
        """Release new version of TumbleSLE by syncing from openQA instance to TumbleSLE server."""
        log.debug("Releasing new TumbleSLE: Build %s" % self.release_build)
        # # do release
        # TODO in openQA as soon as there is comment access over API:
        #   - tag new build
        #   - remove last tag (or update)
        #
        build_dest = os.path.join(self.args.dest, self.release_build) + '/'
        self.sync(build_dest)
        self.update_symlinks(build_dest)
        self.update_release_info()
        log.debug("Release DONE")
        self.notify({'build': self.release_build}, topic='release')
        if self.args.post_release_hook:
            log.debug("Calling post_release_hook '%s'" % self.args.post_release_hook)
            check_call(self.args.post_release_hook)


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
    parser.add_argument('--post-release-hook',
                        help="Specify application path for a post-release hook which is called after every successful release",
                        default=None)
    parser.add_argument('--seen-maxlen', type=int,
                        help="""The length of the 'seen' buffer for notifications. Any AMQP notification is stored in a FIFO and
                        before sending it is checked if the notification was already sent out recently with same content.
                        Together with '--sleeptime' the interval under which the same message would be resent can be configured,
                        e.g. maxlen*sleeptime = minimum time of reappearence (s)""",
                        default=500)
    add_load_save_args(parser)
    return parser.parse_args()


def main():  # pragma: no cover, only interactive
    args = parse_args()
    tr = TumblesleRelease(args)
    tr.run()


if __name__ == "__main__":
    main()
