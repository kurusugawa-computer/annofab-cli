# Usage for Developer
開発者用のドキュメントです。
ソースコードの生成、テスト実行、リリース手順などを記載します。

# 開発方法
VSCodeのdevcotainerを利用して開発します。
https://code.visualstudio.com/docs/remote/containers

1. 以下の環境変数を定義する
    * `ANNOFAB_PAT` : Annofabのパーソナルアクセストークン


# Test

## テストの実行方法
1. 以下のコマンドを実行して、テスト用のプロジェクトとタスクを作成する。

```
$ git clone https://github.com/kurusugawa-computer/annofab-api-python-client.git
$ uv run python annofab-api-python-client/tests/create_test_project.py --organization ${MY_ORGANIZATION}
```

2. `pytest.ini`に、テスト対象のプロジェクトとタスクを指定するを指定する。
    * `task_id`はプロジェクト`project_id`配下であること
3. `$ make test`コマンドを実行する。
    * **【注意】テストを実行すると、Annofabプロジェクトの内容が変更されます**

# Versioning
annofabcliのバージョンはSemantic Versioning 2.0に従います。

annofabcliのバージョンは以下のファイルで定義しています。
* `pyproject.toml`

# Release
GitHubのReleasesからリリースしてください。
バージョンはSemantic Versioningに従います。
リリースすると自動的にPyPIへ公開されます。

# 開発フロー
* mainブランチを元にしてブランチを作成して、プルリクを作成してください。mainブランチへの直接pushすることはGitHub上で禁止しています。

# Secret scan
gitleaksでシークレットがコミットされていないかを検査します。

```
$ make gitleaks
```

コミット時にgitleaksを実行する場合は、pre-commit hookをインストールしてください。

```
$ uv run pre-commit install
```
