import asyncio
from annofabcli.job.wait_job import WaitJobMain
from annofabapi.resource import Resource
from annofabapi.models import ProjectJobType

# AnnofabAPIの認証情報に応じてResourceを作成してください
# 例: service = Resource("user_id", "password")
service = Resource("YOUR_USER_ID", "YOUR_PASSWORD")

# 複数のプロジェクトIDを指定
project_ids = [
    "project_id_1",
    "project_id_2",
    "project_id_3",
]

job_type = ProjectJobType.GEN_INPUTS  # 例: 任意のジョブタイプに変更してください

async def main():
    wait_job_main = WaitJobMain(service)
    tasks = [
        wait_job_main.wait_until_job_finished_async(
            project_id=project_id,
            job_type=job_type,
            job_id=None,
            job_access_interval=60,
            max_job_access=360,
        )
        for project_id in project_ids
    ]
    results = await asyncio.gather(*tasks)
    for project_id, result in zip(project_ids, results):
        print(f"project_id={project_id}, job_status={result}")

if __name__ == "__main__":
    asyncio.run(main())
