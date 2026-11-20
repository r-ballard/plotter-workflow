# Object imposition diagnostics

| Object | Tracked fixture | Physical validation instructions |
| --- | --- | --- |
| Eight-page booklet | [pocketmod8](pocketmod8/expected.json), including eight vector pages | [PocketMod8](../../../docs/validation/pocketmod8-fixture.md) |
| Cootie catcher | [cootie_catcher](cootie_catcher/expected.json), panel sources and orientation specification | [Cootie orientation](../../../docs/validation/cootie-catcher-orientation-fixture.md) |
| Kaleidocycle | [kaleidocycle](kaleidocycle/README.md), generated orientation and continuity nets | [Kaleidocycle orientation](../../../docs/validation/kaleidocycle-orientation-fixture.md) |

Generated plots belong under ignored `output/hardware-acceptance/`; generated
HP-GL bytes are not regression goldens. Preserve each plot's source inventory,
imposition audit, pen plan, placement and preflight sidecars. Physical acceptance
status is recorded separately from successful software checks.
