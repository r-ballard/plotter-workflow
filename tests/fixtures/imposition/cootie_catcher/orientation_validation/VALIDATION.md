# Cootie-catcher semantic orientation physical validation

This validation is the hardware/fold gate for promoting cootie-catcher slot
orientation from `provisional` to a physically validated state.

The diagnostic sources are generated rather than checked in as 20 nearly
identical SVG files. Every source is vector-only, declares an intrinsic canvas,
and uses canonical SVG-up `(0,-1)`. Selector and reveal sources use triangular
canvases with `up_anchor="vertex:0"`; outer sources use square canvases with
`up_anchor="edge:0"`.

Each source contains four deliberately asymmetric features:

- a prominent arrow from the interior toward semantic top;
- an outline of its intrinsic canvas;
- a triangular mark on source-left and a different multi-stroke mark on
  source-right, making reflection visible; and
- a vector-path family/index identifier (`O1`-`O4`, `S1`-`S8`, `R1`-`R8`).

No SVG `<text>` is used.

## 1. Generate the sources

From the repository root:

```bash
uv run python scripts/generate_cootie_orientation_fixture.py --overwrite
```

This creates:

```text
output/cootie_orientation_validation/
  cootie.json
  expected_orientation.json
  physical_validation.template.json
  panels/
    outer-1.svg ... outer-4.svg
    selector-1.svg ... selector-8.svg
    reveal-1.svg ... reveal-8.svg
```

`cootie.json` intentionally contains **no** `rotation_degrees` overrides. If an
override is introduced, the job is no longer a valid test of semantic
orientation.

## 2. Impose the diagnostic job

```bash
uv run python cootie_impose.py \
  output/cootie_orientation_validation \
  --manifest cootie.json \
  --sheet-size letter \
  --square-position left \
  --guides \
  --output output/cootie_orientation_validation.imposed.svg \
  --overwrite
```

Before plotting, validate that the audit sidecar proves semantic orientation was
actually used:

```bash
uv run python scripts/check_cootie_orientation_audit.py \
  output/cootie_orientation_validation.imposed.imposition.json
```

The checker must report 20 semantic-orientation panels, including 16 triangular
panels. It rejects legacy fallback, explicit rotation overrides, missing
intrinsic canvas metadata, or non-canonical source up-vectors.

## 3. Inspect the flat artifacts

Open both outputs before conversion:

```text
output/cootie_orientation_validation.imposed.svg
output/cootie_orientation_validation.imposed.guides.svg
```

Confirm:

- all 20 IDs are present exactly once;
- no panel appears reflected in the flat layout;
- triangular artwork is clipped to its assigned polygon;
- the construction guide and artwork occupy the same square; and
- `expected_orientation.json` agrees with the sidecar's policy, target vectors,
  and resolved rotations.

This inspection is not the physical validation. It only catches obvious source
or imposition mistakes before plotting.

## 4. Convert and preflight as separate jobs

Convert the production artwork using the normal preserved-layout DPX-3300 path.
Use the repository's current known-good converter options for the physical paper
position being used. Convert the guide independently because guide geometry may
reach trim/fold boundaries.

Run the normal job preflight on each HP-GL artifact before transmission. Do not
merge construction-guide pen assignment into the production artwork job.

## 5. Plot, trim, and fold

Use sacrificial Letter paper. Plot the artwork and, if needed, the construction
guide. Trim to the square and perform the complete cootie-catcher fold.

For every visible state, use the asymmetric markers rather than memory of the
flat SVG:

- the arrow must point toward the intended reading top;
- the source-left triangle must still be on the reader's left;
- the source-right multi-stroke mark must still be on the reader's right;
- `S1` must correspond to `R1`, ..., `S8` to `R8`.

A left/right reversal is a reflection defect, not merely a rotation defect.

## 6. Record observations

Copy the generated template rather than editing the template in place:

```bash
cp \
  output/cootie_orientation_validation/physical_validation.template.json \
  output/cootie_orientation_validation/physical_validation.json
```

For each slot record:

- `upright_after_fold`: `true` or `false`;
- `mirrored_after_fold`: `true` or `false`;
- `required_rotation_correction_degrees`: `0`, `90`, `180`, or `270` clockwise
  as viewed by the reader, or `null` if not yet determined;
- `pairing_correct`: for selectors/reveals, whether the semantic pairing is
  correct; and
- free-form `notes` for ambiguous fold/view states.

Set `validation_status` to `complete` only after all 20 slots have been
physically inspected.

## 7. Promotion rule

Software tests and a clean sidecar do **not** change the object-level validation
state. Promote target orientations from `provisional` only when the completed
physical observation record demonstrates:

- all required panels are upright in their intended folded reading state;
- no panel is reflected;
- selector/reveal pairings are correct; and
- any necessary target-vector corrections have been encoded and re-tested.

Keep the completed observation record as the physical validation artifact. Do
not replace semantic regression fixtures with exact vpype path or HP-GL byte
serialization.
