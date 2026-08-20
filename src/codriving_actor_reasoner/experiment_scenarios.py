def create_environment(gym_module, scenario):
    if scenario == "highway":
        return gym_module.make("highway-v0")
    if scenario == "intersection":
        return gym_module.make("intersection-multi-agent-v0")
    if scenario == "merge":
        return gym_module.make(
            "merge-multi-agent-v0",
            config={
                "simulation_frequency": 20,
                "policy_frequency": 5,
                "duration": 40
            }
        )
    raise ValueError(f"Unsupported scenario: {scenario}")
