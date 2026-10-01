==========================================
Codex Skill
==========================================

Codexからannofab-cliを使ってAnnofabのプロジェクト、入力データ、タスク、アノテーションなどを操作・分析するためのAgent Skillを提供しています。

Skillのファイルは、annofab-cliリポジトリの ``skills/annofab-cli-user-operations`` ディレクトリにあります。
``SKILL.md`` だけでなく、コマンド索引などの関連ファイルも使用するため、ディレクトリ全体をインストールしてください。


インストール
==========================================

Linux環境で以下のコマンドを実行します。
GitHubからSkillディレクトリだけをダウンロードして、Codexの個人用Skillディレクトリへ展開します。

.. code-block:: console

    $ mkdir -p ~/.codex/skills
    $ curl --fail --location --silent --show-error https://github.com/kurusugawa-computer/annofab-cli/archive/refs/heads/main.tar.gz \
        | tar -xz --strip-components=2 -C ~/.codex/skills annofab-cli-main/skills/annofab-cli-user-operations

インストール先は ``~/.codex/skills/annofab-cli-user-operations`` です。


関連情報
==========================================

* `CodexにおけるSkillの配置例 <https://developers.openai.com/blog/eval-skills>`_
