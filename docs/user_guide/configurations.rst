==========================================
Configurations
==========================================

認証情報の設定
==================================================================
Annofabにはパーソナルアクセストークンで認証する方法と、ユーザーIDとパスワードで認証する方法があります。
パーソナルアクセストークンの作成方法は https://annofab.readme.io/docs/profile-personal_access_token を参照してください。


Annofabの認証情報を設定する方法は以下の3つです。優先順位が高い順に並べています。

1. コマンドライン引数
2. 環境変数
3. 標準入力（ユーザーIDとパスワード）



コマンドライン引数
----------------------------------------------------------------

ユーザーIDとパスワードによる認証
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::
    
    $ annofabcli my_account get --annofab_user_id alice --annofab_password password


``--annofab_user_id`` のみ指定した場合は、標準入力からパスワードの入力を求められます。


.. code-block::
    
    $ annofabcli my_account get --annofab_user_id alice
    Enter Annofab Password:


パーソナルアクセストークンによる認証
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::
    
    $ annofabcli my_account get --annofab_pat xxxxxxxxxxxxxxxxxxx




環境変数
----------------------------------------------------------------

ユーザーIDとパスワードによる認証
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
環境変数 ``ANNOFAB_USER_ID`` にAnnofabのユーザID , ``ANNOFAB_PASSWORD`` にAnnofabのパスワードを設定してください。


パーソナルアクセストークンによる認証
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
環境変数 ``ANNOFAB_PAT`` にパーソナルアクセストークンを設定してください。


標準入力
----------------------------------------------------------------
コマンドライン引数と環境変数のどちらにも認証情報が設定されていない場合は、標準入力からAnnofabのユーザーIDとパスワードを入力できるようになります。

.. code-block::

    $ annofabcli task list --project_id prj1
    Enter Annofab User ID: XXXXXX
    Enter Annofab Password:



エンドポイントURLの設定（開発者用）
==================================================================
環境変数 ``ANNOFAB_ENDPOINT_URL`` でAnnofab WebAPIのエンドポイントURLを設定することができます。
デフォルトは https://annofab.com です。

コマンドライン引数 ``--endpoint_url`` エンドポイントURLを指定することもできます。

.. code-block::

    $ annofabcli task list --endpoint_url http://localhost:8080
