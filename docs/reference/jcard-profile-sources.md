# J-card profile dimension sources

Checked 2026-10-28. All six Standard Cassette PDFs were downloaded over HTTPS
with certificate verification enabled, rendered with Inkscape, and visually
inspected on both pages. Page 1 is FRONT; page 2 is BACK. Source PDFs remain
ignored research artifacts, not redistributed repository files.

[Standard Cassette template catalogue](https://standardcassette.com/templates).

## Nominal geometry

All formats have a labeled trim height of 4 inches (101.6 mm). Widths below are
front order. Every back page explicitly reverses that order and physical panel
numbers. Native artwork remains upright. Physical roles are back/tracklisting
flap, spine, front cover, then zero or more inward-folded panels.

| Panels | Widths in sixteenths of an inch | Exact total width (mm) |
| --- | --- | ---: |
| 3 | 16, 8, 41 | 103.1875 |
| 4 | 17, 8, 41, 40 | 168.275 |
| 5 | 17, 8, 41, 40, 39 | 230.1875 |
| 6 | 17, 8, 41, 40, 39, 38 | 290.5125 |
| 7 | 17, 8, 41, 40, 39, 38, 37 | 349.25 |
| 8 | 17, 8, 41, 40, 39, 38, 37, 36 | 406.4 |

The five-panel total label is rounded to 9.063 inches. Its individual labels sum
to exactly 9.0625 inches; use that sum, not the rounded headline. Three-panel flap
is exactly 1 inch. Do not obtain it by truncating the eight-panel dimensions.

These files confirm the new Standard Cassette profiles. They do not establish
new NAC profiles: preserve the previously verified `nac-jcard-8-panel-v1` and
name the new records `standard-jcard-N-panel-v1`, including a Standard eight-panel
record. Identical nominal geometry does not imply identical manufacturer stock
or physical acceptance.

## Guides and allowances

Both faces show cyan trim/fold geometry, green type-safety regions and red outer
bleed. The strip is the cyan trim rectangle, not the PDF page. All twelve renders
show the same guide convention. On the six-panel vector inspection, cyan trim is
823.5 by 288 PDF points, exactly 11.4375 by 4 inches. Red bleed expands it by 9
points per exterior edge, or 3.175 mm. Green safety centers are approximately
4.46?4.50 points inside trim/seams; the existing workflow's nominal 1.5875 mm
(4.5 points) inset remains a configurable diagnostic convention, not a claim that
all PDF guide centers are exactly 4.5 points apart. No safety/bleed dimensions are
printed as authoritative tolerance labels. Production clips to trim; actual bleed
artwork and manufacturing tolerances remain outside this feature.

The reverse views show panel N through panel 1 and the same nominal dimensions.
Use the existing explicit paper-flip transform for sheet placement; do not mirror
strokes merely to imitate reversed panel order. Inkscape reported outlined/UTF16
text warnings on import, but dimension labels and geometry were rendered and
inspected successfully. Initial single-page renders were followed by explicit
`--pages=2` imports for back verification.

## Retrieved files and SHA-256

Each linked PDF contains both faces.

| Panels | Download | SHA-256 |
| --- | --- | --- |
| 3 | [PDF](https://standardcassette.com/templates/3-Panel-J-Card-Template.pdf) | `13d838d64f7021af1864bc470e5ba7ef9913a4d9901b3b77726f95a014161d61` |
| 4 | [PDF](https://standardcassette.com/templates/4-Panel-J-Card-Template.pdf) | `c20395b4b160874c118407a369fb1248e9c2ade27bee946bca37299a23a467ca` |
| 5 | [PDF](https://standardcassette.com/templates/5-Panel-J-Card-Template.pdf) | `e6b0d3079205bd1e1c36131fd25aca0c323b760c9d700523e239419bf6660111` |
| 6 | [PDF](https://standardcassette.com/templates/6-Panel-J-Card-Template.pdf) | `597b3aabf78e500a0a4f67bda0f338feb0bafae19461cabe7b7f68b0c3d2349a` |
| 7 | [PDF](https://standardcassette.com/templates/7-Panel-J-Card-Template.pdf) | `00dd73b19dec097175e5e77ecae43d0abb02dc99d3c7f59108ec5dd9cc310180` |
| 8 | [PDF](https://standardcassette.com/templates/8-Panel-J-Card-Template.pdf) | `7c0d2e1bbe00c0c327fe1f64efaba6ba6ee8485a02e07f9422d9d0b369b325ee` |

## Existing NAC profile

The NAC eight-panel dimensions and original front/back source hashes remain in
[cassette-jcard.md](cassette-jcard.md). Local NAC downloads currently fail an
expired-certificate check. The user explicitly required keeping verification
strict and supplied Standard Cassette as the alternative. No TLS bypass or
persistent certificate change was used. Standard data is not relabeled as NAC.

Research artifacts: `output/jcard-profile-reference/standard-N.pdf`,
`standard-N.png`, `standard-N-back.png`, `standard-sources.json`, and the
six-panel vector import `standard-6.svg`. Physical fit/duplex proof remains HAR-88.
