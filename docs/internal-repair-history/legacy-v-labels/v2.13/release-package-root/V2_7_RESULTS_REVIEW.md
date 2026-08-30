# v2.7 returned verification review

The v2.7 numerical suite completed successfully. The radiative feedback decomposition is now
internally consistent and should be frozen unless later tests demonstrate a new problem.

Key returned values:

- Equilibrium-tail GMST (1100-1200 y): 3.2099 C, but tail TOA = -0.5104 W/m2 (not equilibrium).
- Gregory 1-150 y effective ECS = 2.8482 C, feedback = 1.2257 W/m2/K.
- TCR = 1.9218 C.
- Planck = -3.2658; WV = +1.8102; resolved LR = -0.4642;
  polar inversion closure = +0.0316; WV+LR+polar = +1.3777;
  albedo = +0.2932; cloud = +0.4356; net = -1.1594 W/m2/K.
- Hosing 0.5 Sv: AMOC minimum ~0 Sv, cold blob -4.091 C.
- Persistent post-hosing branch after 800 y without hosing: AMOC ~0 Sv,
  cold-blob diagnostic -10.982 C (too extreme).
- Energy residual = 0.0339%.
- Pycnocline final imbalance = 1.9e-6 Sv.
- Reference-residual heat correction <2e-16 W/m2 equivalent.

The major v2.7 ECS issue is coupled AMOC drift, not radiative-feedback tuning. Under constant
2xCO2 the AMOC falls from 17 Sv to 9.04 Sv at y300, 7.97 at y600, 6.22 at y900,
3.89 at y1100 and 1.66 Sv at y1200. This coincides with progressive northern freshening and
invalidates the 1200-y tail as a clean radiative equilibrium ECS.
