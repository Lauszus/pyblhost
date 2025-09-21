You can run all tests by running:

```bash
make test
```

Additional arguments can be passed to pytest by using the `PYTEST_ARGS` environment variable.
For example, to run only the `test_pyblhost` test:

```bash
make test PYTEST_ARGS="-k test_pyblhost"
```

To run a specific test:

```bash
make test PYTEST_ARGS="-k test_upload_file_reading"
```

After you have made any changes, please use ruff to fix the formatting and check for lint errors:

```bash
make -j ruff-fix
```

Once that is done, you should make sure the code does not have any mypy errors:

```bash
make mypy
```
