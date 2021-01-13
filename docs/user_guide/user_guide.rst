==========================================
User Guide
==========================================


Command Structure
==========================================


.. code-block::

    $ annofabcli <command> <subcommand> [options and parameters]

* ``command`` : ``project`` や ``task`` など家庭ゴリに対応します。
* ``subcommand`` : 実行する操作に対応します。



Version
==========================================

``--version`` を指定すると、annofabcliのバージョンが表示されます。

.. code-block::

    $ annofabcli --version
    annofabcli 1.39.0



Getting Help
==========================================
``--help`` を指定すると、コマンドのヘルプが表示されます。


.. code-block::

    $ annofabcli --help

    usage: annofabcli [-h] [--version] {annotation,annotation_specs,...} ...

    Command Line Interface for AnnoFab

    positional arguments:
      {annotation,annotation_specs,...}
        annotation          アノテーション関係のサブコマンド
        annotation_specs    アノテーション仕様関係のサブコマンド
        ...

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit


.. code-block::

    $ annofabcli task --help

    usage: annofabcli task [-h] {cancel_acceptance,change_operator,...} ...

    タスク関係のサブコマンド

    positional arguments:
      {cancel_acceptance,change_operator,...}
        cancel_acceptance   受入が完了したタスクに対して、受入を取り消します。
        change_operator     タスクの担当者を変更します。

    optional arguments:
      -h, --help            show this help message and exit


.. code-block::

    $ annofabcli task list --help
    usage: annofabcli task list [-h] [--yes] [--endpoint_url ENDPOINT_URL] [--logdir LOGDIR] [--disable_log] [--logging_yaml LOGGING_YAML] -p PROJECT_ID [-tq TASK_QUERY | -t TASK_ID [TASK_ID ...]] [-u USER_ID [USER_ID ...]] [-f {csv,json,pretty_json,task_id_list}]
                                [-o OUTPUT] [--csv_format CSV_FORMAT] [-q QUERY]

    タスク一覧を出力します。

    optional arguments:
      -h, --help            show this help message and exit
      -p PROJECT_ID, --project_id PROJECT_ID
                            対象のプロジェクトのproject_idを指定します。 (default: None)

    global optional arguments:
      --yes                 処理中に現れる問い合わせに対して、常に'yes'と回答します。 (default: False)



パラメータの指定
=================================================
複数の値を渡せるコマンドラインオプションと、JSON形式の値を渡すコマンドラインオプションは、``file://`` を指定することでファイルの中身を渡すことができます。

.. code-block::
    :caption: task_id.txt

    task1
    task2


.. code-block::

    # 標準入力で指定する
    $ annofabcli task list --project_id prj1 --task_id task1 task2

    # 相対パスでファイルを指定する
    $ annofabcli task list --project_id prj1 --task_id file://task_id.txt


.. code-block::
    :caption: /tmp/task_query.json

    {
        "status":"not_started",
        "phase":"acceptance"
    }


.. code-block::

    # 標準入力で指定
    $ annofabcli task list --project_id prj1 --task_query '{"status":"not_started", "phase":"acceptance"}'

    # 絶対パスでファイルを指定する
    $ annofabcli task list --project_id prj1 --task_query file:///tmp/task_query.json



ロギングコントロール
=================================================

デフォルトのログ設定は以下の通りです。

* ログメッセージは、標準エラー出力とログファイル ``.log/annofabcli.log`` に出力されます。
* ``annofabcli.log`` ファイルは、1日ごとにログロテート（新しいログファイルが生成）されます

詳細なログの設定は https://github.com/kurusugawa-computer/annofab-cli/blob/master/annofabcli/data/logging.yaml を参照してください。


ログファイルの出力先を変更する場合は、``--logdir`` にログファイルの出力先ディレクトリを指定してください。

ログ設定をカスタマイズする場合は、``--logging_yaml`` にロギング設定ファイルを指定してください。
設定ファイルの書き方は https://docs.python.org/ja/3/howto/logging.html を参照してください。


以下のロギング設定ファイルを指定すると、WARNINGレベル以上のログのみコンソールに出力します。


.. code-block:: yaml
    :caption: logging.yaml

    version: 1
    handlers:
      consoleHandler:
        class: logging.StreamHandler
    root:
      level: WARNING
      handlers: [consoleHandler]

    # デフォルトのロガーを無効化しないようにする https://docs.djangoproject.com/ja/2.1/topics/logging/#configuring-logging
    disable_existing_loggers: False


.. code-block::

    $ annofabcli task list --project_id prj1 --loging_yaml loggin.yaml
