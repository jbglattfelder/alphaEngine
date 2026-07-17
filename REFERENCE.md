# X-accounting reference numbers (bit-check targets)

**RE-BASELINED 2026-07-15** on the `close_mode="home"` default (the flip resolves
HANDOFF-v4 §5's live trap). The previous table was generated on the quantity
path and is retired; quantity remains available as the named treatment
`close_mode="quantity"`.

Config per row: Config(f=<f>, c=0.004, T=6000, seed=<seed>, x_accounting=True, log_thresholds=True, symmetric_solvency=True)  # close_mode defaults "home"

| f | seed | p_final (full precision) | drift ln(p/x0) | long X-share |
|---|------|--------------------------|----------------|--------------|
| 0.3 | 1 | np.float64(3.4145279771117274e-08) | -17.192641 | 0.300000 |
| 0.3 | 2 | np.float64(1.5113000739620497) | +0.412970 | 0.540717 |
| 0.3 | 3 | np.float64(5.686853241735516) | +1.738157 | 0.640346 |
| 0.3 | 4 | np.float64(2.974382857270011e-06) | -12.725474 | 0.300001 |
| 0.5 | 1 | np.float64(0.0005895985292513698) | -7.436069 | 0.500008 |
| 0.5 | 2 | np.float64(0.08331088641502116) | -2.485176 | 0.500246 |
| 0.5 | 3 | np.float64(0.4245626718502022) | -0.856696 | 0.500135 |
| 0.5 | 4 | np.float64(0.0017477617032882222) | -6.349419 | 0.500048 |
| 1.0 | 1 | np.float64(3.982355415776321e-06) | -12.433637 | 0.999996 |
| 1.0 | 2 | np.float64(0.22081746589221038) | -1.510419 | 0.819204 |
| 1.0 | 3 | np.float64(3.827259569156836e-09) | -19.381117 | 1.000000 |
| 1.0 | 4 | np.float64(2.117962981573481e-08) | -17.670226 | 1.000000 |
