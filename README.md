![test](https://github.com/os-autoinst/openqa_review/actions/workflows/python-package.yaml/badge.svg)
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/699/badge)](https://bestpractices.coreinfrastructure.org/projects/699)



A review helper script for openQA.

For more details read the documentation within `openqa_review/openqa_review.py`.

## Usage

* Install requirements and package, using an isolated Python environment
  such as [VirtualEnv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

```
pip3 install -r requirements.txt
pip3 install .
```

To call the script from the git clone, you have to use this form:

```
python3 -m openqa_review.openqa_review
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

If that doesn't work, you can try the following setting:
```
CURL_CA_BUNDLE=""
```

## Communication

If you have questions, visit #opensuse-factory on [libera.chat](https://web.libera.chat/).


## Contribute

This project lives in https://github.com/os-autoinst/openqa_review

Feel free to add issues in github or send pull requests.

TODOs and ideas are tracked in the file `TODO` as well as github issues.

## How to run tests

Tests are implemented on top of [pytest](https://docs.pytest.org/en/6.2.x/) and
[tox](https://tox.wiki/en/latest/). Tox can be invoked with no arguments to test
all environments:

```
tox
```

It is also possible to run only a special environment, e.g. `tox -e flake8` for
the linter, `tox -e py38` for running tests at the specified Python version (the
interpreter needs to be installed for this version) or `tox -e cov` for the
coverage report (see details below). These environments are configured in
`tox.ini`.

To ensure files are passing the style check, invoke `black .` to apply
correct formatting.

If you are running into issues installing dependencies (resulting in an error
like "Could not build wheels…"), try to remove the temporary `.tox` directory
(or the subfolder for the problematic environment within).

### Run tests via `pytest`
You can also run the tests via `pytest` with one of the following commands:

```
pytest
# or
python3 -m pytest
# or, after running tox at least once:
./.tox/cov/bin/py.test
```

To test only certain functions, there are several possibilities:
```
pytest tests/test_openqa_review.py::test_reminder_comments_on_referenced_bugs_are_posted
pytest -k test_reminder_comments_on_referenced_bugs_are_posted
```

### Generate coverage report
Run the following commands to generate a coverage report under `coverage_html/`:

```
tox -e cov
./.tox/cov/bin/coverage html
```

### Rules for commits

* Every commit is checked by a [GitHub Workflow](https://github.com/os-autoinst/openqa_review/actions)
  as soon as you create a pull request but you *should* run `tox` locally,

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
