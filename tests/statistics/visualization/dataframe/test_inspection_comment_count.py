import json
from pathlib import Path

from annofabcli.statistics.visualization.dataframe.inspection_comment_count import InspectionCommentCount

output_dir = Path("./tests/out/statistics/visualization/dataframe/inspection_comment_count")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class Test__InspectionCommentCount:
    def test__from_api_content(self):
        with open(data_dir / "inspection-comment.json", encoding="utf-8") as f:
            inspection_comment = json.load(f)

        actual = InspectionCommentCount.from_api_content(inspection_comment)
        assert len(actual.df) == 1
        row = actual.df.iloc[0]
        assert row["inspection_comment_count_in_inspection_phase"] == 0
        assert row["inspection_comment_count_in_acceptance_phase"] == 1
