# DeFi Risk from Scratch (course PDF)

Source of `docs/DeFi_Risk_from_Scratch.pdf`: a course on every blockchain and DeFi concept the
project uses, for readers with no background.

- `kit.py`: layout (fonts, styles, callout boxes, tables, diagrams, charts)
- `part1.py` … `part5.py`: the five parts and the appendices
- `build.py`: cover, contents, assembly (three passes so the contents has the right page numbers)

Rebuild (from the repo root):

    pip install reportlab
    python docs/course/build.py

Fonts are read from macOS (`/System/Library/Fonts/Supplemental/Arial*.ttf`, `Menlo.ttc`); on
another system, point the paths at the top of `kit.py` to equivalent TTF fonts.

The "Real numbers" boxes were computed with the code at commit ff651d1 on the cached snapshots in
`data/cache/`. Update them when the model changes.
