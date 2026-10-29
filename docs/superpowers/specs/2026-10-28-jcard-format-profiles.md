# Manufacturer J-card format profiles

Date: 2026-10-28. Follow-on to merged plotter-workflow PR18, baseline
`e3f3cb0`. Work branch: `feat/jcard-format-profiles` in the retained isolated
`jcard-object` worktree. Status: proposed design; no product changes yet.

## Goal

Support the manufacturer's 3-, 4-, 5-, 6- and 7-panel cassette J-cards alongside
the existing eight-panel insert. Each format supports front, back or both faces,
independent or continuous artwork per face, optional guides and separate plotting
jobs. Physical plotting remains deferred acceptance work.

The user approved extending the named-profile approach. A free-form panel-count
control is outside scope: smaller templates are not necessarily truncated copies
of the eight-panel template. A separate renderer for each format would duplicate
the existing artwork, provenance, conversion and paper-flip contracts.

## Profile data and shared behavior

Add immutable, explicitly enumerated profile records keyed by
`nac-jcard-{3..8}-panel-v1`. Each record owns exact nominal panel widths, height,
physical panel roles, source references and safe/bleed reference allowances.
Record source hashes after successful downloads. Do not ship downloaded PDFs.

Use rational or Decimal dimensions before conversion to float. Do not infer all
formats through a decrement formula, even where verified widths happen to match.
Keep the current eight-panel profile and default selection valid.

Derive normalized slots, native width, seven-or-fewer seams, front/back ordering,
artwork windows and source coverage from the selected record. Slots remain
`front-panel-N` / `back-panel-N`; physical IDs remain `panel-N`. Back native
ordering reverses the selected format's physical panel order.

The same selected profile must drive configuration, placement, artwork export,
bindings, restoration and imposition. Remove hardcoded eight-panel checks and
406.4/1536 geometry from shared paths. Require exactly the selected profile's
panels, and reject wrong-format assets even when individual panel sizes match.

Keep both existing paper-flip matrices, with the profile's resolved W/H replacing
eight-panel constants. Never resize artwork to fit a sheet. Keep face-alone versus
paired output determinism, guide-layer collision checks, explicit blank masking,
atomic publication and the established converter sidecar contract.

No automatic sheet selection. Smaller profiles can fit Letter/A4 when their trim
and enabled marks fit the explicitly configured drawable area; larger profiles
still require a sufficiently large sheet. Validate using resolved physical sizes.

## Source verification

Manufacturer catalogue:
https://www.nationalaudiocompany.com/cassette-duplication/prepare-your-audio-and-your-album-art/cassette-art-templates/

Browser research retrieved the catalogue and the following template text:

| Format | Retrieved nominal front widths (inches) | Research status |
| --- | --- | --- |
| 3 | 1, 1/2, 2 9/16 | Front/back labels retrieved; flap differs from eight-panel profile |
| 4 | 1 1/16, 1/2, 2 9/16, 2 1/2 | Front labels and 6.625 × 4 inch live area retrieved; back needs verification |
| 5 | 1 1/16, 1/2, 2 9/16, 2 1/2, 2 7/16 | Front/back width labels and reverse ordering retrieved |
| 6 | Not yet independently verified | Front PDF resolves but extracted text is empty; back fetch failed |
| 7 | Not yet independently verified | Front total 13.75 × 4 inches retrieved; individual widths/back still need verification |
| 8 | Existing verified record from PR18 | Retain current exact geometry |

The three-panel labels imply 103.1875 mm total width, versus 104.775 mm for the
first three panels of the eight-panel record. Verify guide geometry, trim height,
safe/bleed offsets and face orientation visually for every new record before
implementation fixes its constants. PDF page size is not trim size.

Direct downloads with Python and Windows HTTPS both failed certificate trust
validation on 2026-10-28. Browser research can retrieve several PDFs. Keep TLS
validation enabled; resolve retrieval or use accessible authoritative browser
renders before declaring remaining measurements verified. Research scratch is
retained under `output/jcard-profile-reference/`.

Official Illustrator/PDF filenames under `/wp-content/uploads/2017/08/`:

- `NAC_3-Panel_JCard_FRONT_forAI.pdf` / `NAC_3-Panel_JCard_BACK_forAI.pdf`
- `NAC_4-Panel_Jcard_FRONT_Template_forAI_040313.pdf` / corresponding `BACK`
- `NAC_Jcard_5-Panel_FRONT_Template_forAI_050513.pdf` / corresponding `BACK`
- `NAC_Jcard_6-Panel_FRONT_Template_AI5.pdf` / corresponding `BACK`
- `NAC_Jcard_7-Panel_FRONT_Template_AI5.pdf` / corresponding `BACK`

## Delivery and verification

Provide a dimension/profile table, complete JSON examples for each new profile,
and generated guide-only and front/back artwork samples. Include an example on
Letter/A4 for a fitting smaller profile and A3/tabloid for larger profiles.
Document physical panel count separately from printed face selection.

Use focused tests for each profile's exact widths/totals, nonoverlap/seams,
reversed back order, off-center flip corner identities, safe/registration fit,
blank/sparse dimensions, mixed-profile rejection, deterministic face selection,
atomic paired publication and converter acceptance. Run affected J-card and
artwork/imposition consumers before a PR; no transport/full-generator baseline.

Reuse existing neutral producer recipes without a cassette-specific generator.
Keep the unrelated minor blank-source viewport issue in HAR-89. Extend the
physical acceptance checklist in HAR-88 to record format-specific paper proofs;
software geometry does not prove stock, fold allowance or case fit.

After design approval, write a native implementation plan, then implement in the
isolated branch with scoped regression checks and one final branch review.
