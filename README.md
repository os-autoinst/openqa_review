# openqa_review_script [![Build Status](https://travis-ci.com/os-autoinst/openqa_review.svg?branch=master)](https://travis-ci.com/os-autoinst/openqa_review) [![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/699/badge)](https://bestpractices.coreinfrastructure.org/projects/699)

A review helper script for openQA.

For more details read the documentation within `openqa_review/openqa_review.py`.

## Usage

* Install requirements and package, using an isolated Python environment
  such as [VirtualEnv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

```
pip3 install -r requirements.txt
pip3 install .
```

or if you are using openSUSE distribution, it is recommended to use `zypper`,
e.g.:

```
zypper in python-openqa_review
```

* Call `openqa-review` from PATH, e.g. with `--help`

```
openqa-review --help
```

If `openqa-review` has to access non public servers which make use of custom
*Certificate Authorities* (CA's), it can happen that it fails because it can
not verify the TLS certificate. By setting the environment variable
`REQUESTS_CA_BUNDLE`, one can supply a custom ca-certificate store to
`openqa-review` e.g.:

```
REQUESTS_CA_BUNDLE="/my/custom/ca-bundle.pem" openqa-review
```

## Communication

If you have questions, visit me on irc.freenode.net in #opensuse-factory


## Contribute

This project lives in https://github.com/os-autoinst/openqa_review

Feel free to add issues in github or send pull requests.

TODOs and ideas are tracked in the file `TODO` as well as github issues.

### Rules for commits

* Every commit is checked by [Travis CI](https://travis-ci.com) as soon as
  you create a pull request but you *should* run `tox` locally,

* Make sure to keep the 100% test coverage, e.g. by adding test reference data
  for new scenarios. TDD is advised :-)

* For git commit messages use the rules stated on
  [How to Write a Git Commit Message](http://chris.beams.io/posts/git-commit/) as
  a reference

If this is too much hassle for you feel free to provide incomplete pull
requests for consideration or create an issue with a code change proposal.

## License

This project is licensed under the MIT license, see LICENSE file for details.
Exceptions are the files under `dashboard_files/` which are GPL-2 licensed
coming from https://github.com/os-autoinst/openQA/.
