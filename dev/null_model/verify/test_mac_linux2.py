from simulation_mvp import Config, Simulation
sim = Simulation(Config(n=500, T=5000, seed=17, capital_dist="pareto",
                        band_dist="normal"), run_checks=False).run()
print(repr(sim.rec_price[1200]), repr(sim.rec_price[4800]))
# Linux says: 88.33411404732354   28.09458199472048


from simulation_mvp import Config, build_agents
ags = build_agents(Config(n=500, seed=17, capital_dist="pareto", band_dist="normal"))
print(repr(ags[0].tp_band), repr(ags[250].sl_band), repr(ags[499].tp_band))
