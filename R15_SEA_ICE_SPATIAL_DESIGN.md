# R15 sea-ice spatial-scope decision

The current CLEM sea-ice state resolves latitude and two broad ocean sectors but does not carry enough longitudinal degrees of freedom to treat satellite 15%-threshold *extent* as an independently validated physical prediction. R15 therefore keeps extent diagnostic and non-release-blocking.

A future spatial extension is scientifically justified, but it should be a distinct model-version change rather than an empirical R15 patch. The minimum defensible design is a conservative multiregion Arctic state with at least Atlantic/Barents, central-Eurasian, Pacific/Chukchi, and Canadian-Archipelago sectors across the existing latitude bands. Each region would prognose concentration/volume with shared latent-heat and freshwater conservation, explicit inter-region ice export, and grid-cell area occupancy. Satellite extent would then be computed by the same 15% threshold operator without an area-to-extent multiplier.

That extension requires new coupled numerical validation and is intentionally not conflated with the confirmed R15 AMOC/Greenland repairs.
