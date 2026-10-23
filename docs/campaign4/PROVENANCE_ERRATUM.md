# Development baseline provenance correction

The development engineer initially described
`data/campaign4-development/original-source` as an exact original source archive.
The manager's source-hash audit showed that its `workflows/service.py` already
contained the first boundary repair. Its SHA-256 is
`a0516b603a246647c529ee87af8343f33a0321993aef36dc41801f239812c5ac`,
while the actual `0aede83` file is
`4bd6e5f0cdcc1659523329bfcba96fe1d61c0d386e27942b835dbba4669fe9a2`.
The development engineer acknowledges the mistaken provenance label.

All existing archives, receipts and scores remain preserved without changes.
The first fixture-error run, corrected 120-case run, five-case supplement and
65 after-projection transaction probes are intermediate-source evidence rather
than pure original baseline evidence. The direct reference probe used the
original reference bytes, but it is also being repeated within the verified
complete original environment.

The manager's pre-edit `source.zip` contains all 192 original modules. New
original runs import exclusively from its extracted package at
`data/campaign4-manager/original-source/extracted/src`. They record the imported
package location and all source hashes before and after execution. Their new
directories are `true-original-cycle3`, `true-original-supplement`,
`true-original-protocol` and `true-original-transition-faults` under
`data/campaign4-development`. Frozen development inputs and oracles are unchanged.

Final reports use this verified original baseline, retain the intermediate
results separately, and do not treat a prior mixed-source run as original.
