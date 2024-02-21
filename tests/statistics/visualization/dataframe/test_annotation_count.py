from pathlib import Path

from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount

output_dir = Path("./tests/out/statistics/visualization/dataframe/annotation_count")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class Test__AnnotationCount:
    def test__from_annotation_zip(self):
        actual = AnnotationCount.from_annotation_zip(data_dir / "simple-annotations.zip", "prj1")
        assert len(actual.df) == 2
        row = actual.df.iloc[0]
        assert row["annotation_count"] == 2
