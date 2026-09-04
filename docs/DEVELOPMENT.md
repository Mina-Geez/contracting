# Developing Insite

For people changing the app. [SETUP.md](./SETUP.md) is for people running it.

## The two halves of the gate

```bash
# offline — no site needed
python -m pytest insite/tests -q     # 62 tests
ruff check insite
ruff format --check insite
node --check insite/public/js/insite_transaction.js

# on a bench — 14 integration tests
bench --site test.localhost migrate
bench --site test.localhost run-tests --app insite
```

Run both before pushing. The integration tests live beside the doctype they
cover (`insite/insite/doctype/scope_item/test_scope_item.py`), which is where
Frappe looks for them. `pytest` never collects them, because it is pointed at
`insite/tests`.

## What the offline half proves

This gate proves the pure calculation code (`insite/calc/measures.py` and
`resolve.py` import no Frappe) and the app's structure — that every DocType has a
controller, that `field_order` matches `fields`, that Select options match the
constants the code compares against, that JSON timestamps have been bumped, and
that no stray control characters have crept into the source.

**It proves nothing about Frappe.** Every install failure this app has had, and
both bugs found on 2026-09-04, were invisible to it:

| Bug | Why the gate missed it |
| --- | --- |
| An aggregate written as a field string — `fields=["sum(x) as y"]` | Frappe v16 rejects it at runtime. Valid Python. It took the whole Contract Progress report down, not just its column. |
| Word boundaries written as literal backspace bytes | Valid Python, invisible in an editor and in `git diff`. Every rule summary silently showed `height * width * count` instead of `Height × Width × Count`. |

So: **run anything that touches a Frappe or ERPNext API on a real bench before
pushing.** A guard test now covers the second one. The first is what a bench is
for.

### Two sites, and why

| Site | For |
| --- | --- |
| `test.localhost` | `bench run-tests`. Bare — **never run the setup wizard on it.** |
| `dev.localhost` | Looking at the app: the setup wizard, a company, demo data. |

They have to be separate. ERPNext's test bootstrap builds its own fixtures
(`_Test Company`, the standard price lists), and on a site the setup wizard has
already populated it dies with `DuplicateEntryError: ('Price List', 'Standard
Buying')` before a single test runs.

Three more things `bench run-tests` needs:

- `bench --site test.localhost set-config allow_tests true`, or it refuses.
- The **`payments`** app installed. ERPNext's bootstrap references the Payment
  Gateway doctype, which moved out of ERPNext in v15, and without it discovery
  fails with `DoesNotExistError: DocType Payment Gateway not found`.
- `pytest` importable in the bench venv. Discovery imports every test module in
  the app, including the offline ones, and stops at `No module named 'pytest'`.

### Writing integration tests

Two traps, both of which produced tests that passed alone and failed together:

- **Look fixtures up by their unique field, not by name.** Project and Scope Item
  are named by series, so `frappe.db.exists("Project", "My Project")` never
  matches and the second run dies on the unique constraint.
- **Clean up in `tearDown`.** Committing shared fixtures in `setUpClass` takes
  the class outside Frappe's per-test rollback, so anything a test creates
  survives into the next one. The report test then totals every leftover
  inspection, and the invoice warning — which names five and then says "and
  more" — stops naming the one the test just made.

## Getting a bench

### Toolchain floors

Frappe v16 needs more than most distributions ship. Neither floor is announced.
Both surface as confusing failures.

| | v16 needs | Ubuntu 24.04 ships |
| --- | --- | --- |
| Python | **>= 3.14, < 3.15** | 3.12 |
| Node | **>= 24** | 20 |

- Wrong Python: `uv` refuses with *"Because the current Python version (3.12.3)
  does not satisfy Python>=3.14 … frappe==16.33.0 cannot be used."*
- Wrong Node: `yarn install` fails with *"The engine node is incompatible with
  this module. Expected version >=24"* — after every Python package has installed,
  so it looks like an asset problem rather than a version one.

`bench` itself also shells out to **`uv`** and does not install it. Without it,
`bench init` dies with `FileNotFoundError: 'uv'`.

### A bench from scratch

Verified on Ubuntu 24.04 (WSL2), 2026-09-04.

```bash
# system
sudo apt-get install -y python3-dev python3-venv build-essential \
    redis-server mariadb-server mariadb-client libmariadb-dev pipx
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo bash -   # node >= 24
sudo apt-get install -y nodejs && sudo npm install -g yarn

# MariaDB needs these for Frappe
sudo tee /etc/mysql/mariadb.conf.d/99-frappe.cnf >/dev/null <<'CONF'
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
[mysql]
default-character-set = utf8mb4
CONF
sudo systemctl restart mariadb

# bench, and a Python it will accept
pipx install frappe-bench
pipx install uv
uv python install 3.14

bench init frappe-bench --frappe-branch version-16 --python "$(uv python find 3.14)"
cd frappe-bench
bench get-app erpnext --branch version-16
bench new-site dev.localhost --db-root-password <pw> --admin-password <pw>
bench --site dev.localhost install-app erpnext
```

Run bench as an ordinary user, never root.

### The app itself

The app does not need to be copied into the bench. A symlink works, and keeps
one authoritative copy of the code:

```bash
ln -s /path/to/contracting frappe-bench/apps/insite
frappe-bench/env/bin/python -m pip install -e frappe-bench/apps/insite
printf 'frappe\nerpnext\ninsite\n' > frappe-bench/sites/apps.txt
bench --site dev.localhost install-app insite
bench --site dev.localhost migrate
```

This works even when the source sits on a mounted network share, and the
editable install leaves no build artefacts in the repo.

### Gotchas

- **bench runs its own Redis**, on the ports in `config/redis_*.conf` (not the
  system one on 6379). `bench migrate` fails with *"Service redis_cache is not
  running"* until they are up — `bench start`, or
  `redis-server config/redis_cache.conf --daemonize yes` for each config.
- `bench new-site` needs `sites/apps.txt` to exist. A `bench init` that aborted
  part-way never writes it, and every later command then fails with
  `OSError: ./apps.txt Not Found`.
- An aborted `bench init` asks whether to roll back. Non-interactively that
  prompt reads EOF and it aborts **without** rolling back, so the half-built
  bench survives and can be repaired rather than rebuilt.

### The alternative: containers

[frappe_docker](https://github.com/frappe/frappe_docker) pins the whole
toolchain in its images, so none of the version-floor problems above exist. It is
the more reproducible option, and worth preferring if you want an environment
that can be recreated identically on another machine. The trade is an extra layer
between you and `bench`, which matters when the app source lives outside the
container.

## Arabic

The product is bilingual. `insite/locale/ar.po` holds the Arabic, and
`bench build --app insite` compiles it to a `.mo`.

Two tests keep it honest, because a translation file rots without anyone
noticing. One says every string the app shows is either translated or on the
short list of standard Frappe labels that Frappe's own Arabic already covers.
The other says an Arabic message keeps the same `{0}` placeholders as its
English, so it still formats with a row number in it.

Two things to know when adding a string:

- **One literal per `_()` or `__()` call.** A concatenation reaches a
  translator as fragments, and a fragment is not a sentence.
- `bench generate-pot-file` does not work on a symlinked app. It takes a path
  relative to the bench, and the real path is outside it. The tests extract the
  strings themselves, so run them and read what they list as missing.

## Checking a Frappe API before you rely on it

Frappe's own APIs shift between versions, and a wrong shape is a runtime error
that no offline check sees. Before writing an unfamiliar call into the app, run
it against a real instance first, then transcribe what worked. The query builder
is preferred over both `get_all` field-string aggregates and new raw SQL:

```python
from frappe.query_builder.functions import Sum

t = frappe.qb.DocType("Quality Inspection")
rows = (
    frappe.qb.from_(t)
    .select(t.scope_item, Sum(t.custom_rejected_amount).as_("amount"))
    .where(t.status == "Rejected")
    .groupby(t.scope_item)
    .run(as_dict=True)
)
```

## Architecture

See **For developers** in the [README](../README.md).
