from pathlib import Path

from annofabcli.statistics.list_annotation_duration import ListAnnotationDurationByInputData
from annofabcli.statistics.visualize_video_duration import plot_video_duration

output_dir = Path("./tests/out/statistics/visualize_video_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)



def test__plot_video_duration() -> None:
    durations = [60]*10 + [120]*5 + [180]*2
    
    plot_video_duration(
        durations,
        output_file=output_dir / "test__plot_video_duration.html",
    )

