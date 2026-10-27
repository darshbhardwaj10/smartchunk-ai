"""Compatibility wrapper for the full offline evaluation suite."""
from evaluation_data.evaluate import main
if __name__ == '__main__':
    raise SystemExit(main(['--suite', 'all']))
