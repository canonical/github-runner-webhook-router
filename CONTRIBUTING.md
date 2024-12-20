# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create an environment for development with `tox`:

```shell
tox devenv -e integration
source venv/bin/activate
```

## Repository structure

The repository contains the charm code in the `charm` directory and the code for the workload
in the root directory. The charm directory has been built using the
[`paas-charm`](https://juju.is/docs/sdk/12-factor-app-charm) approach and then modified to support
the specific actions of this charm.


## Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox run -e fmt        # update your code according to linting rules
tox run -e lint          # code style
tox run -e unit          # unit tests
tox run -e integration   # integration tests
tox                      # runs 'fmt', 'lint', and 'unit' environments
```

The integration tests require additional parameters which can be looked up in the `tests/conftest.py` file.
Some of them have environment variable counterparts (see `tests/integration/conftest.py`),
which can be set instead of passing them as arguments, which is more secure for sensitive data.

There is also a `tox` root in the `charm` directory, which can be used to lint and format the charm code:

```shell
cd charm
tox run -e fmt        # update your code according to linting rules
tox run -e lint       # code style
```

## Development server

Flask contains a development server that can be used to test the charm. To start the server, run:

```shell
  python -m src.app
```
in your virtual environment and project root.


## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

<!-- You may want to include any contribution/style guidelines in this document>
