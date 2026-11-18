# Contributing

Thanks for taking the time to contribute.

## License of contributions

This repository is released under **GPL-3.0** (see `LICENSE`).

By submitting a pull request, patch, or any other contribution, you agree that
your contribution is licensed under the same license as this repository
(inbound = outbound). You keep your copyright; you do not transfer it.

If you cannot agree to this, please open an issue first instead of sending code.

## Practical guidelines

- Keep changes focused; one topic per pull request.
- Match the existing code style and keep user-facing text bilingual where the
  project already is.
- Do not add dependencies with licenses incompatible with GPL-3.0.
- Do not paste code from Stack Overflow or other projects unless the license is
  compatible and you note the source in the pull request.
- Run the test suite before submitting:

  ```powershell
  python -m unittest discover -s tests
  ```

## Reporting issues

Please include the Windows version, Python version, model/provider used, and the
relevant log lines. Never paste API keys.
