# Installation

## Requirements

- Python 3.12 or higher
- A Readwise account with API access

## Install from PyPI

```bash
pip install readwise-plus
```

### With CLI Support

To use the command-line interface, install with the `cli` extra:

```bash
pip install readwise-plus[cli]
```

### Using uv

If you're using [uv](https://github.com/astral-sh/uv) for package management:

```bash
uv add readwise-plus
# or with CLI
uv add readwise-plus[cli]
```

## Development Installation

To install from source for development:

```bash
git clone https://github.com/EvanOman/readwise-plus.git
cd readwise-plus
uv sync --dev
```

## Verify Installation

```python
import readwise_sdk
print(readwise_sdk.__version__)
```

Or with the CLI:

```bash
readwise version
```

## Next Steps

- [Authentication](authentication.md) - Set up your API key
- [Quick Start](quickstart.md) - Start using the SDK
