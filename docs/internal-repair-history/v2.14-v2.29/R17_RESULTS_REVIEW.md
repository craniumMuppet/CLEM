# R17 numerical results review

R17 completed all 11 requested experiments. The prognostic sea-ice support state substantially reduced the R16 summer extent inflation but retained an unphysical compactness seasonality: the modern March pack was less compact than September and March extent remained too large/flat. The fixed-mask validator also still thresholded native concentration instead of using the new fractional support occupancy.

Matched-pathway TEOS-10 remained substantially less sensitive than the validated linear closure (about 13.03 Sv after 0.2 Sv hosing and 12.91 Sv at SSP2-4.5 year 2100 versus roughly 9.51 and 8.25 Sv for the linear branch). Linear therefore remains the production default; TEOS is structural sensitivity evidence.

The collapsed AMOC branch did not recover by year 700 for de-hosing of -0.05, -0.10, or -0.20 Sv. This is not treated as proof of a bug or repaired with a restart threshold. R18 maps stronger de-hosing to identify the reduced-model recovery neighborhood and tests persistence after forcing removal.
