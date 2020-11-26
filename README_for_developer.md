# Usage for Developer
開発者用のドキュメントです。
ソースコードの生成、テスト実行、リリース手順などを記載します。

# Requirements
* Bash
* python 3.6+

# Install
以下のコマンドを実行してください。開発に必要な環境が構築されます。

```bash
$ make init
```

# Test

## テストの実行方法
1. AnnoFabの認証情報を、`.netrc`ファイルまたは環境変数に設定する。
2. 以下のコマンドを実行して、テスト用のプロジェクトとタスクを作成する。

```
$ git clone https://github.com/kurusugawa-computer/annofab-api-python-client.git
$ poetry run python annofab-api-python-client/tests/create_test_project.py --organization ${MY_ORGANIZATION}
```

3. `pytest.ini`に、テスト対象のプロジェクトとタスクを指定するを指定する。
    * `task_id`はプロジェクト`project_id`配下であること
4. `$ make test`コマンドを実行する。
    * **【注意】テストを実行すると、AnnoFabプロジェクトの内容が変更されます**

# Versioning
annofabcliのバージョンはSemantic Versioning 2.0に従います。

annofabcliのバージョンは以下のファイルで定義しています。
* `annofabcli/__version__.py`
* `pyproject.toml`


# PyPIへのリリース方法

## 事前作業

### PyPIのアカウントを作成
1. 以下のURLにアクセスして、PyPIのアカウントを作成する。
https://pypi.org/account/register/

2. 管理者に連絡して、Collaboratorsとして招待してもらう
https://pypi.org/project/annofabcli/

## リリース方法
以下のコマンドを実行してください。PyPIのユーザ名とパスワードの入力が求められます。

```
$ make publish
```


# 開発フロー
* masterブランチを元にしてブランチを作成して、プルリクを作成してください。masterブランチへの直接pushすることはGitHub上で禁止しています。
* リリース時のソースはGitHubのRelease機能、またはPyPIからダウンロードしてください。




-----------------
# リリースする手順

### 1.テストの実施
「テストの実行方法」を参照してください。

### 2.versionを上げる
「Versioning」を参照して、バージョンを上げたプルリクを作成してください。TavisCIが通ったらマージしてください。

### 3.PyPIへパッケージをアップロード
「PyPIへのリリース方法」を参照してください。

### 4.GitHubのリリースページに追加
GitHubのReleaseページで、リリースを作成してください。
https://github.com/kurusugawa-computer/annofab-cli






