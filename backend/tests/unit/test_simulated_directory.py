from cyrvanta.modules.directory.infrastructure import simulated_provider


def test_simulated_directory_provider_is_not_exported() -> None:
    assert simulated_provider.__all__ == ()
    assert not hasattr(simulated_provider, "SimulatedDirectoryProvider")
