"""Per-output durable request cap. Reserve before submission; unknown is never retried."""
import json
from pathlib import Path


class GenerationBudget:
    def __init__(self, directory: Path, limit: int = 6):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 120:
            raise ValueError('Image budget must be between 1 and 120')
        self.directory = Path(directory) / 'generation-ledger'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.limit = limit

    def reserve(self, identity: str) -> Path:
        for path in self.directory.glob('request-*.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record['identity'] == identity and not path.with_suffix('.done').exists():
                raise RuntimeError('Previous submission unknown; reconcile before another request')
        for index in range(self.limit):
            path = self.directory / f'request-{index}.json'
            try:
                with path.open('x', encoding='utf-8') as stream:
                    json.dump({'identity': identity, 'status': 'reserved_unknown'}, stream)
                return path
            except FileExistsError:
                continue
        raise RuntimeError(f'Image budget exhausted; maximum {self.limit} submissions including failures')

    def complete(self, ticket: Path) -> None:
        ticket.with_suffix('.done').touch(exist_ok=False)
