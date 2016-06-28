#!/usr/bin/env python
from openqa_review import ...

# generate report as dict
# save report as jsonpickle
# add option to openqa_review to save/output content as json instead of markdown, could be yaml, too

# for every unlabeled issue investigate

## investigate
# based on https://progress.opensuse.org/projects/openqav3/wiki/Wiki#Further-decision-steps-working-on-test-issues

# * product changes
# use command like
# env arch=s390x old=1616 new=1621 base=Beta2 vimdiff http://xcdchk.suse.de/browser/data/SLE-12-SP2-Server/Build${old}/${arch}/ChangeLog-${base}-Build${old}.txt http://xcdchk.suse.de/browser/data/SLE-12-SP2-Server/Build${new}/${arch}/ChangeLog-${base}-Build${new}.txt
#
# also check for existance of satsolver reports, e.g. http://xcdchk.suse.de/browser/data/SLE-12-SP3-Desktop/Build0209/x86_64/SATSOLVER.short.txt which can
# shortcut the detection process. It seems if the file exists we already know what's wrong, where the installation would fail
#
# * test software changes
# tricky, we don't yet have a git commit for the revision of the tests distribution used, see https://github.com/os-autoinst/os-autoinst/pull/393

    changes in test setup, e.g. our test hardware equipment behaves different or the network

    changes in test infrastructure software, e.g. os-autoinst, openQA

    changes in test management configuration, e.g. openQA database settings

    changes in the test software itself
