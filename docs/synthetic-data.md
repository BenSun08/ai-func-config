# Mica anchor orders

Mica is a fictional demonstrator with two controllers. Its catalog covers lighting,
stop requests and a multistate shelf dial. The twelve development cases are small
enough to check against the fixed revisions by hand. All engineering values were
invented for this suite.

## Reading an order

Open the [engineering world](../synthetic/worlds/core.yaml). The keys under each
function's `revisions` are the eligible alternatives in release `MICA-K1`.
Select one versioned entry under `orders` for the order material. Its row IDs
and the table headers identify current, historical and planned statements.
For example, `M32-r1 / P32.B` means the full contents of cell B6 on the
`pins` sheet of that order. D6 on the same row records a historical connection.
Whole cells preserve the original wording and enclosing conditions. The native manifest
records the file hashes. Ingestion assigns parser-generated source block IDs.

The only authored application material is the world catalog and the requested
order. M38 includes the submitted rows under review. M42 includes the prior
decision that the change request addresses. The [reference file](../evals/gold/anchors.json)
is a separate, evaluator-only document with source relationships, issue codes,
the acceptable result and the reasoning for each case. A reference result can
specify acceptable complete selection maps, a resolved exclusion, a required
abstention or a rejected submission.

### Loading fixture inputs

The [input manifest](../synthetic/worlds/manifest.json) pins the catalog ID,
the order IDs and the SHA-256 of the authored YAML. Give the fixture loader the
manifest's directory and one order ID. It returns the shared catalog and that
order's source material, including any submitted rows or historical decision
that belongs to the order.

```python
from pathlib import Path
from synthetic.inputs import load_order_input

source = load_order_input(Path("synthetic/worlds"), "M32-r1")
pin_cells = source["orders"]["M32-r1"]["rows"]["P32"]["cells"]
```

The directory contains exactly `manifest.json` and `core.yaml`. The loader
rejects extra files, symlinks, digest or inventory mismatches, evaluator
annotations and gold paths. When editing engineering inputs, review the source
change before repinning its digest. The renderer iterates over the scoped inputs
from a single verified read. The evaluator, tests and this answer-bearing guide
live outside the application distribution. T16 owns the application image and
its build-context exclusions.

### Inspecting the native files

From the repository root, run:

```sh
uv run python -m synthetic.renderers.fixtures --suite anchors --output runtime/anchors
```

The [canonical pack](../tests/fixtures/anchors/manifest.json) contains 22 workbooks
and one Word library. The command writes the same engineering material to the
requested directory. An identical existing pack can be reused. If a pack was
edited or contains other files, render to a fresh directory to preserve those edits.
The manifest pins each file's SHA-256, role, business revision and layout profile.
For an order table it also maps authored row IDs to native rows and locates the
column headers. The scope band sits immediately above those headers.

| Open | What to inspect |
| --- | --- |
| [M32-r1 pin sheet](../tests/fixtures/anchors/orders/M32-r1/pins.xlsx) | B6 is the current DIAL-A connection. D6 records historical DIAL-B. E6 is planned use. |
| [Logic sheet](../tests/fixtures/anchors/orders/M32-r1/logic.xlsx) and [switch sheet](../tests/fixtures/anchors/orders/M32-r1/switches.xlsx) | B8 keeps the awake-only 0/2/5/0 cycle and the sleep exception in one multiline cell. The momentary mechanism and PETAL switch model occupy B5 and D5 on the switch sheet. |
| [Function library](../tests/fixtures/anchors/knowledge/function-library.docx) | Each function heading owns its revision headings and field/value tables. |
| [Attributes](../tests/fixtures/anchors/knowledge/attributes.xlsx) and [experience](../tests/fixtures/anchors/knowledge/experience.xlsx) | Inspect the typed candidate values, decision roles, hardware catalog, reviewed rules and timed composition trace. Sequence and mapping cells use JSON. |

Give a consumer the shared `knowledge/` files and one `orders/` directory.
The plan's public demo path `orders/E01` contains business revision `M31-r1`.
The other directories use their business revision IDs. M38 includes both original
submission rows. M42 includes the historical parent decision and its separate
current change request. Keep answer lookups in the offline evaluator.

### Independent evaluation

The offline [split manifest](../evals/splits.json) assigns whole families to
partitions. The suite loader checks every case's declared split against that
assignment. All four current families are public development examples. The
validation and test partitions are empty until independent families are authored.
Add a paraphrase or related order to its existing family.

| Case | Engineering question | Hand-checked outcome |
| --- | --- | --- |
| E01 | Which dial revision meets the binding, contact and full cycle? | LEVEL-A.1 alone. |
| E01.three-table | Does the same revision meet the clauses spread across the pin, logic and switch sheets? | LEVEL-A.1 alone, despite ranking second on each row. |
| E02 | Does a signed, explicitly false trim entry exclude the tag? | Exclude F-TAG under FIT.1. |
| E03 | Does a slash on the signed form establish fitment? | Leave F-TAG empty and ask whether it is fitted. |
| E04 | Can the beacon accept momentary contacts and reset on CLEAR? | Abstain. The two clauses are covered by different alternatives of F-BEACON. |
| E04.positive | Can a lens preference compensate for a failed reset? | Abstain. Both revisions fail a necessary condition. |
| E05 | Can the two beacon endpoints use different mechanisms? | Abstain. The fixed harness applies one mechanism to both. |
| E06 | Can one submission select two revisions of INK? | Reject the duplicate function rows before constructing a map. |
| E07 | Can the order distinguish the two eligible chalk-socket drivers? | Abstain for review. Both remain candidates. |
| E08 | Can the detector and lamp jointly implement a timed request? | SEND.1 and PULSE.1, one per function, through released template RELAY.1. |
| E09 | Can the counter coexist with an independently required steady lamp? | Choose STORE.1 and DC.1. SEND.1 would require an incompatible lamp. |
| E10 | What lamp demand survives the change to local-only counting? | Select STORE.1 alone. No active dependency or derived lamp demand remains. |

## Checking the two comparison cases

For **E01.three-table**, start with `M32-r1`. Its pin row specifies DIAL-A as
the current binding. Its logic row requires the awake-only 0/2/5/0 cycle. Its
switch row specifies a momentary contact. B fails the contact, C fails the
binding and D skips level 2. The hand-authored rank lists use a small diagnostic
policy, `literal-catalog-terms-v1`. Within the shelf-dial family, count each
distinct catalog term appearing in the lowercased current cells of one row once.
Sort by decreasing count and then by revision ID. At a cutoff of one, the three
rows return B, C and D respectively. These ranks are fixture expectations for
the stated policy. T09.3 will measure the operational retrieval paths.

For **E04.positive**, compare the four current cells identified in the reference
against each beacon revision. Each observation contributes once under
`signed-typed-v1`: an exact typed match scores +1 and a confirmed mismatch
scores −1. GLINT matches three observations and fails reset, yielding +2.
SHADE matches two and fails contact and lens, yielding 0. Lens is a preference.
Reset and contact are required, so the checked draft leaves F-BEACON empty.

Run `uv run pytest tests/acceptance/test_anchor_integrity.py -q` for the
reference integrity checks. Offline callers can load the hand-authored cases
with `from evals.types import build_anchor_suite`. The loader reads the
reference file without invoking retrieval, scoring or planning.
