# Usage for Developer
開発者用のドキュメントです。
ソースコードの生成、テスト実行、リリース手順などを記載します。

# 開発方法
VSCodeのdevcotainerを利用して開発します。
https://code.visualstudio.com/docs/remote/containers

1. 以下の環境変数を定義する
    * `ANNOFAB_USER_ID` : AnnofabのユーザID
    * `ANNOFAB_PASSWORD` : Annofabのパスワード
    * `DATA_DIR` : devcontainer外のファイルにアクセスしたい場合、そのファイルの存在するディレクトリを指定してください。devcontainerでは`/data`でアクセスできます。この環境変数は`devcontainer.json`でしか参照されていません。https://github.com/kurusugawa-computer/annofab-cli/blob/62c6bb420d50b7ef87aa2074ca040b118ed60c80/.devcontainer/devcontainer.json#L20


# Test

## テストの実行方法
1. Annofabの認証情報を、`.netrc`ファイルまたは環境変数に設定する。
2. 以下のコマンドを実行して、テスト用のプロジェクトとタスクを作成する。

```
$ git clone https://github.com/kurusugawa-computer/annofab-api-python-client.git
$ uv run python annofab-api-python-client/tests/create_test_project.py --organization ${MY_ORGANIZATION}
```

3. `pytest.ini`に、テスト対象のプロジェクトとタスクを指定するを指定する。
    * `task_id`はプロジェクト`project_id`配下であること
4. `$ make test`コマンドを実行する。
    * **【注意】テストを実行すると、Annofabプロジェクトの内容が変更されます**

# Versioning
annofabcliのバージョンはSemantic Versioning 2.0に従います。

annofabcliのバージョンは以下のファイルで定義しています。
* `pyproject.toml`

# Release
GitHubのReleasesからリリースしてください。
バージョンはSemantic Versioningに従います。
リリースすると、以下の状態になります。

* ソース内のバージョン情報（`pyproject.toml`）は、https://github.com/ninoseki/uv-dynamic-versioning でGitHubのバージョンタグから生成されます。
* 自動でPyPIに公開されます。

# 開発フロー
* mainブランチを元にしてブランチを作成して、プルリクを作成してください。mainブランチへの直接pushすることはGitHub上で禁止しています。

