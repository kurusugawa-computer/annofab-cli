==========================================
Getting Started
==========================================

annofabcliは、Annofabのプロジェクト、入力データ、タスク、アノテーションなどを操作するコマンドラインツールです。
利用するには、Annofabのアカウントが必要です。


動作環境
==========================================

* Python 3.11以上


インストール
==========================================


.. code-block:: console

    $ pip install annofabcli


インストールの確認
==========================================

以下のコマンドでバージョンが表示されれば、インストールは完了です。

.. code-block:: console

    $ annofabcli --version
    annofabcli 1.130.0


認証情報の設定
==========================================

Annofab APIへのアクセスには認証が必要です。
パーソナルアクセストークン、ユーザーIDとパスワード、環境変数、 ``.netrc`` ファイルを利用できます。
設定方法と優先順位は :doc:`configurations` を参照してください。

たとえば、環境変数にパーソナルアクセストークンを設定します。

.. code-block:: console

    $ export ANNOFAB_PAT='xxxxxxxxxxxxxxxxxxx'


初回の動作確認
==========================================

認証情報を設定後、まず自分のアカウント情報を取得します。

.. code-block:: console

    $ annofabcli my_account get

次に、自分が所属する組織を確認できます。

.. code-block:: console

    $ annofabcli organization list

各コマンドの詳細は :doc:`../command_reference/my_account/get` および :doc:`../command_reference/organization/list` を参照してください。
利用できるコマンドは :doc:`../command_reference/index` に一覧があります。


