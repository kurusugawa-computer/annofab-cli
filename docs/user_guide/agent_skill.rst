==========================================
Agent Skill
==========================================

AIエージェントからannofab-cliを使ってAnnofabのプロジェクト、入力データ、タスク、アノテーションなどを操作・分析するためのAgent Skillを提供しています。

Skillのファイルは、annofab-cliリポジトリの ``skills/annofab-cli-user-operations`` ディレクトリにあります。
``SKILL.md`` だけでなく、コマンド索引などの関連ファイルも使用するため、ディレクトリ全体をインストールしてください。


Codexへのインストール
==========================================

Linux環境で以下のコマンドを実行します。
GitHubからSkillディレクトリだけをダウンロードして、Codexの個人用Skillディレクトリへ展開します。

.. code-block:: console

    $ mkdir -p ~/.codex/skills
    $ curl --fail --location --silent --show-error https://github.com/kurusugawa-computer/annofab-cli/archive/refs/heads/main.tar.gz \
        | tar -xz --strip-components=2 -C ~/.codex/skills annofab-cli-main/skills/annofab-cli-user-operations

インストール先は ``~/.codex/skills/annofab-cli-user-operations`` です。


Claude Codeへのインストール
==========================================

Linux環境で以下のコマンドを実行します。
GitHubからSkillディレクトリだけをダウンロードして、Claude Codeの個人用Skillディレクトリへ展開します。

.. code-block:: console

    $ mkdir -p ~/.claude/skills
    $ curl --fail --location --silent --show-error https://github.com/kurusugawa-computer/annofab-cli/archive/refs/heads/main.tar.gz \
        | tar -xz --strip-components=2 -C ~/.claude/skills annofab-cli-main/skills/annofab-cli-user-operations

インストール先は ``~/.claude/skills/annofab-cli-user-operations`` です。
Claude Codeで ``/annofab-cli-user-operations`` を入力すると、Skillを呼び出せます。


Gemini CLIへのインストール
==========================================

Gemini CLIのSkillインストールコマンドで、リポジトリ内のSkillディレクトリを指定します。
``--scope user`` を指定すると、すべてのプロジェクトで利用できます。

.. code-block:: console

    $ gemini skills install https://github.com/kurusugawa-computer/annofab-cli.git \
        --path skills/annofab-cli-user-operations --scope user

インストール先は ``~/.gemini/skills/annofab-cli-user-operations`` です。
起動済みのGemini CLIに反映するには、対話セッションで ``/skills reload`` を実行します。
``/skills list`` で ``annofab-cli-user-operations`` が表示されることを確認できます。


関連情報
==========================================

* `CodexにおけるSkillの配置例 <https://developers.openai.com/blog/eval-skills>`_
* `Claude CodeのSkillドキュメント <https://code.claude.com/docs/en/skills>`_
* `Gemini CLIのSkillドキュメント <https://geminicli.com/docs/cli/skills/>`_
