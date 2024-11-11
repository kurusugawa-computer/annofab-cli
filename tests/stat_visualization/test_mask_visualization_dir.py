from pathlib import Path

from annofabcli.stat_visualization.mask_visualization_dir import mask_visualization_dir
from annofabcli.statistics.visualization.project_dir import ProjectDir, TaskCompletionCriteria

output_dir = Path("./tests/out/stat_visualization/mask_visualization_dir")
data_dir = Path("./tests/data/stat_visualization/mask_visualization_dir")
output_dir.mkdir(exist_ok=True, parents=True)


def test__mask_visualization_dir__minimal():
    mask_visualization_dir(
        project_dir=ProjectDir(data_dir / "visualization1", TaskCompletionCriteria.ACCEPTANCE_COMPLETED),
        output_project_dir=ProjectDir(output_dir / "masked-visualization", TaskCompletionCriteria.ACCEPTANCE_COMPLETED),
        minimal_output=True,
    )
