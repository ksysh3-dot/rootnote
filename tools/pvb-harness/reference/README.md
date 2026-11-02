# Fixed host reference

Build from the repository root:

```sh
bash tools/pvb-harness/build_host.sh tools/pvb-harness/build-reference --reference
```

Only the C API library has `PVB_HOST_RESULTANT_REFERENCE=1`; JNI and both Android
flavors compile only P1 (ID 6) and P1+++ (ID 6 + param 57). The optional C API also
accepts ID 16, the modified Resultant v1.6-c. Its fixed 30-value vector is in
`VbHpv::setAlpha2Profile`, with 1-based parameters 27, 28 and 29 all 1, param 30 = 0.
This is s50 source 9d408fb plus the fixes already implemented there, enabled here.
The API setter rejects arbitrary Resultant vectors; old v1.5/a/b/d and redistribution
experiments must use annotated archive/models-pre-prune-20261102 (9d408fb).
The source length/F1 contract remains checked at compile time.

For a PCM comparison use `s56/compare.py` or the fixed `s56/render.py` entry point.
Historical research scripts and their original fixtures remain available at the
archive tag, not in current CI. No historical output is re-labelled as a new result.
