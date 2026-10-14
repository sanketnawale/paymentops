# Test fixtures

Real bank payload fixtures (XML / JSON / CSV) will be added here as the mapping and
validation engines are built in later phases. They are kept separate from tests so they
can be reused across unit/integration suites.

Treat every fixture payload as **untrusted** input.

- `*.xml`, `*.json`, `*.csv` — sample inbound payloads for mapping/validation.
- `*.schema.json` — expectation files with expected canonical output.

No real, sensitive payment data belongs here.
