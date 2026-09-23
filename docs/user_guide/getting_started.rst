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
以下のように自分自身のアカウント情報が出力されれば、認証情報は正しく設定されています。

.. code-block:: console

    $ annofabcli my_account get
    {
        "account_id": "***",
        "user_id": "***",
        "username": "***",
        "email": "***",
        "reset_requested_email": null,
        "lang": "ja-JP",
        "keylayout": "ja-JP",
        "authority": "user",
        "biography": "***",
        "errors": [],
        "updated_datetime": "2026-01-05T14:55:26.248+09:00",
        "account_type": "annofab"
    }    


