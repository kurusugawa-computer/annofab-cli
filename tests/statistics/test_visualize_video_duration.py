from pathlib import Path

from annofabcli.statistics.visualize_video_duration import TimeUnit, plot_video_duration

output_dir = Path("./tests/out/statistics/visualize_video_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)

durations_for_input_data = [60] * 10 + [120] * 5 + [180] * 2
durations_for_input_task = durations_for_input_data[0:-2]


def test__plot_video_duration() -> None:
    plot_video_duration(durations_for_input_data, output_file=output_dir / "test__plot_video_duration.html", time_unit=TimeUnit.SECOND)


def test__plot_video_duration__bin_widthを指定する() -> None:
    plot_video_duration(
        durations_for_input_data,
        output_file=output_dir / "test__plot_video_duration__bin_widthを指定する.html",
        bin_width=60,
        time_unit=TimeUnit.SECOND,
    )


def test__plot_video_duration__time_unitにminuteを指定する() -> None:
    plot_video_duration(
        durations_for_input_data,
        output_file=output_dir / "test__plot_video_duration__time_unitにminuteを指定する.html",
        bin_width=60,
        time_unit=TimeUnit.MINUTE,
    )
