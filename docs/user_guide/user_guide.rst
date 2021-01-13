==========================================
User Guide
==========================================


Command Structure
----------------------------------------------------------------


.. code-block::

    $ annofabcli <command> <subcommand> [options and parameters]

* ``command`` : ``project`` や ``task`` など家庭ゴリに対応します。
* ``subcommand`` : 実行する操作に対応します。



Version
----------------------------------------------------------------
``--version`` を指定すると、annofabcliのバージョンが表示されます。

.. code-block::

    $ annofabcli --version
    annofabcli 1.39.0



Getting Help
----------------------------------------------------------------
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
　　　...

    global optional arguments:
      --yes                 処理中に現れる問い合わせに対して、常に'yes'と回答します。 (default: False)
      ...



パラメータの指定
----------------------------------------------------------------

リスト
^^^^^^^^^^^^
