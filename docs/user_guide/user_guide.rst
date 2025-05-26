==========================================
User Guide
==========================================


Command Structure
==========================================


.. code-block::

    $ annofabcli <command> <subcommand> [options and parameters]

* ``command`` : ``project`` や ``task`` などのカテゴリに対応します。
* ``subcommand`` : ``list`` や ``delete`` など、実行する操作に対応します。



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

    Command Line Interface for Annofab

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
                                [-o OUTPUT]

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
ログメッセージは、標準エラー出力とログファイル ``.log/annofabcli.log`` に出力されます。
``.log/annofabcli.log`` は、1日ごとにログロテート（新しいログファイルが生成）されます。

ログファイルの出力先を変更する場合は、``--logdir`` にログファイルの出力先ディレクトリを指定してください。


``--debug`` を指定すれば、HTTPリクエストも出力されます。

.. code-block::

  $ annofabcli project list -org kurusugawa -o out/project.csv
  INFO     : 2022-01-24 12:27:32,145 : annofabcli.__main__            : sys.argv='['annofabcli', 'project', 'list', '-org', 'kurusugawa', '-o', 'out/project.csv']'
  DEBUG    : 2022-01-24 12:27:34,206 : annofabcli.project.list_project : project_query: {'user_id': 'xxx', 'account_id': 'xxx'}
  INFO     : 2022-01-24 12:27:42,240 : annofabcli.project.list_project : プロジェクト一覧の件数: 384
  INFO     : 2022-01-24 12:27:42,281 : annofabcli.common.utils        : out/project.csv を出力しました。

  $ annofabcli project list -org kurusugawa --debug -o out/project.csv
  INFO     : 2022-01-24 12:28:22,630 : annofabcli.__main__            : sys.argv='['annofabcli', 'project', 'list', '-org', 'kurusugawa', '--debug', '-o', 'out/project.csv']'
  DEBUG    : 2022-01-24 12:28:22,631 : annofabapi.resource            : Create annofabapi resource instance :: {'login_user_id': 'xxx', 'endpoint_url': 'https://annofab.com'}
  DEBUG    : 2022-01-24 12:28:23,133 : annofabapi.api                 : Sent a request :: {'requests': {'http_method': 'post', 'url': 'https://annofab.com/api/v1/login', 'query_params': None, 'request_body_json': {'user_id': 'xxx', 'password': '***'}, 'request_body_data': None, 'header_params': None}, 'response': {'status_code': 200, 'content_length': 4374}}
  DEBUG    : 2022-01-24 12:28:23,133 : annofabapi.api                 : Logged in successfully. user_id = xxx
  DEBUG    : 2022-01-24 12:28:24,996 : annofabapi.api                 : Sent a request :: {'request': {'http_method': 'get', 'url': 'https://annofab.com/api/v1/organizations/kurusugawa/members', 'query_params': None, 'header_params': None, 'request_body': None}, 'response': {'status_code': 200, 'content_length': 42835}}
  DEBUG    : 2022-01-24 12:28:24,996 : annofabcli.project.list_project : project_query: {'user_id': 'xxx', 'account_id': 'xxx'}
  DEBUG    : 2022-01-24 12:28:26,485 : annofabapi.api                 : Sent a request :: {'request': {'http_method': 'get', 'url': 'https://annofab.com/api/v1/organizations/kurusugawa/projects', 'query_params': {'user_id': 'xxx', 'account_id': 'xxx', 'page': 1, 'limit': 200}, 'header_params': None, 'request_body': None}, 'response': {'status_code': 200, 'content_length': 194801}}
  DEBUG    : 2022-01-24 12:28:26,493 : annofabapi.wrapper             : calling 'get_projects_of_organization' :: 2/2 steps
  DEBUG    : 2022-01-24 12:28:27,399 : annofabapi.api                 : Sent a request :: {'request': {'http_method': 'get', 'url': 'https://annofab.com/api/v1/organizations/kurusugawa/projects', 'query_params': {'user_id': 'xxx', 'account_id': 'xxx', 'page': 2, 'limit': 200}, 'header_params': None, 'request_body': None}, 'response': {'status_code': 200, 'content_length': 182546}}
  INFO     : 2022-01-24 12:28:27,409 : annofabcli.project.list_project : プロジェクト一覧の件数: 384
  INFO     : 2022-01-24 12:28:27,441 : annofabcli.common.utils        : out/project.csv を出力しました。



Windowsでannofabcliを実行する
=================================================
annofabcliはWindowsでも実行できます。



インストール
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Python環境がなくてもannoafbcliを実行できるようにするため、Windows用の実行ファイルを用意しています。
https://github.com/kurusugawa-computer/annofab-cli/releases から ``annofabcli-vX.X.X-windows.zip`` をダウンロードして、zip内の ``annofabcli.exe`` を実行してください。


JSON文字列の指定
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
WindowsのコマンドプロンプトやPowerShellでannofabcliを使う場合、JSON文字列内のダブルクォートをエスケープする必要があります。

PowerShellでは、JSON文字列内のダブルクォートを ``\`` でエスケープして、JSON文字列全体をシングルクォートで括ってください。

.. code-block::

    PS >  annofabcli task list --project_id prj --task_query '{\"status\": \"complete\"}'


コマンドプロンプトでは、JSON文字列内のダブルクォートを ``\`` または ``"`` でエスケープして、JSON文字列全体をダブルクォートで括ってください。


.. code-block::

    >  annofabcli task list --project_id prj --task_query "{\"status\": \"complete\"}"

    >  annofabcli task list --project_id prj --task_query "{""status"": ""complete""}"


エスケープ処理の詳細については https://zenn.dev/yuji38kwmt/articles/68ed55564df1f2 を参照ください。


エスケープが面倒な場合は、JSON文字列をファイルに保存して、そのファイルパスを指定する方法がおすすめです。


.. code-block::
   :caption: task_query.json

    {"status": "complete"}


.. code-block::

    PS >  annofabcli task list --project_id prj --task_query file://task_query.json




