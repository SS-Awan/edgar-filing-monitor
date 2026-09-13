import edgar_monitor


def test_package_imports() -> None:
    """The package is available to the test runner."""
    assert edgar_monitor.__doc__ == "EDGAR Filing Monitor pipeline package."