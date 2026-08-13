"""Retired compatibility entry point for the removed synthetic directory bootstrap."""


def main() -> None:
    raise RuntimeError("Synthetic directory bootstrap was retired by PHASE_24")


if __name__ == "__main__":
    main()