from pathlib import Path

from annofabcli.statistics.visualize_video_duration import TimeUnit, plot_video_duration

output_dir = Path("./tests/out/statistics/visualize_video_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)

durations = [60] * 10 + [120] * 5 + [180] * 2


def test__plot_video_duration() -> None:
    durations = [60] * 10 + [120] * 5 + [180] * 2

    plot_video_duration(durations, output_file=output_dir / "test__plot_video_duration.html", bin_count=20)


def test__plot_video_duration__bin_widthを指定する() -> None:
    durations = [60] * 10 + [120] * 5 + [180] * 2

    plot_video_duration(durations, output_file=output_dir / "test__plot_video_duration__bin_widthを指定する.html", bin_width=60)


def test__plot_video_duration__time_unitにminuteを指定する() -> None:
    plot_video_duration(
        durations, output_file=output_dir / "test__plot_video_duration__time_unitにminuteを指定する.html", bin_width=60, time_unit=TimeUnit.MINUTE
    )
