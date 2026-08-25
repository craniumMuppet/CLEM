#!/usr/bin/env python3
"""Regression tests for the v2.17.0 six-Sv AMOC plot reference."""

from pathlib import Path
import tempfile

import matplotlib.pyplot as plt
import numpy as np

from climate_model import AMOC_SIX_SV_REFERENCE, ModelConfig, ProcessClimateModel, save_outputs
from monte_carlo import make_endpoint_histogram, make_endpoint_scatter, make_ensemble_line_figure


def _has_horizontal_line(axis, value: float) -> bool:
    return any(
        np.allclose(np.asarray(line.get_ydata(), dtype=float), value)
        for line in axis.lines
        if np.asarray(line.get_ydata()).size > 0
    )


def _has_vertical_line(axis, value: float) -> bool:
    return any(
        np.allclose(np.asarray(line.get_xdata(), dtype=float), value)
        for line in axis.lines
        if np.asarray(line.get_xdata()).size > 0
    )


def main() -> None:
    years = np.arange(2000.0, 2005.0)
    values = np.vstack([np.linspace(17.0, 5.0, len(years)), np.linspace(16.0, 7.0, len(years))])
    weights = np.array([0.5, 0.5])

    figure = make_ensemble_line_figure(
        years,
        values,
        weights,
        title="AMOC",
        ylabel="AMOC (Sv)",
        reference_line=AMOC_SIX_SV_REFERENCE,
        reference_label="6 Sv reference",
    )
    assert _has_horizontal_line(figure.axes[0], AMOC_SIX_SV_REFERENCE)
    plt.close(figure)

    figure = make_endpoint_histogram(
        values[:, -1],
        weights,
        "Final AMOC",
        "AMOC (Sv)",
        False,
        reference_line=AMOC_SIX_SV_REFERENCE,
        reference_label="6 Sv reference",
    )
    assert _has_vertical_line(figure.axes[0], AMOC_SIX_SV_REFERENCE)
    plt.close(figure)

    figure = make_endpoint_scatter(values[:, 0], values[:, -1], weights, False)
    assert _has_horizontal_line(figure.axes[0], AMOC_SIX_SV_REFERENCE)
    plt.close(figure)

    config = ModelConfig(duration_years=2.0, dt_years=0.25, record_every_years=1.0)
    result = ProcessClimateModel(config).run()
    with tempfile.TemporaryDirectory() as temporary_directory:
        save_outputs(result, temporary_directory)
        assert (Path(temporary_directory) / "amoc_timeseries.png").is_file()
        assert (Path(temporary_directory) / "diagnostics" / "amoc_dynamical_targets.png").is_file()

    print("All v2.17.0 six-Sv reference tests passed.")


if __name__ == "__main__":
    main()
