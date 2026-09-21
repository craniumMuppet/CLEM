# Arctic acquisition core-five continuation patch

The legacy NSIDC-0611 archive can require separate Earthdata application authorization.
That product is a structural multiyear-ice diagnostic, not a calibration target.

This build therefore:

- keeps G02202, PIOMAS, CryoSat-2, ICESat-2, and OSI SAF as mandatory core sources;
- no longer prompts for legacy NSIDC username/password by default;
- does not abort if NSIDC-0611 is unavailable;
- exports `ARCTIC_VALIDATION_DATA_BUNDLE.zip` only if all five core sources are complete;
- records NSIDC-0611 as explicitly missing/pending rather than passed;
- retains the crash log and window-stays-open launcher.

The five-source bundle is sufficient to continue the corrected area/volume/thickness recalibration and OSI SAF cross-dataset development check. The final multiyear-ice structural diagnostic remains incomplete until NSIDC-0611 is separately supplied.
