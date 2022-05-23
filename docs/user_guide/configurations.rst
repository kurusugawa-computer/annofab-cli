==========================================
Configurations
==========================================

認証情報の設定
==================================================================
Annofabの認証情報を設定する方法は2つあります。

* ``.netrc`` ファイル
* 環境変数 ``ANNOFAB_USER_ID`` , ``ANNOFAB_PASSWORD``


.netrc ファイル
----------------------------------------------------------------
`.netrcファイル <https://www.gnu.org/software/inetutils/manual/html_node/The-_002enetrc-file.html>`_ にAnnofabの認証情報を記載してください。

.. code-block::
    :caption: .netrc

    machine annofab.com
    login annofab_user_id
    password annofab_password

For Linux
^^^^^^^^^^^^^^^^^^^^^^^^^
* パスは ``$HOME/.netrc``
* ``$ chmod 600 $HOME/.netrc`` でパーミッションを変更する



For Windows
^^^^^^^^^^^^^^^^^^^^^^^^^
* パスは ``%USERPROFILE%\.netrc``



環境変数
----------------------------------------------------------------
環境変数 ``ANNOFAB_USER_ID`` にAnnofabのユーザID , ``ANNOFAB_PASSWORD`` にAnnofabのパスワードを指定してください。

標準入力
----------------------------------------------------------------
.netrcファイルと環境変数どちらにも認証情報が設定されていない場合は、標準入力からAnnofabの認証情報を入力できるようになります。

.. code-block::

    $ annofabcli task list --project_id prj1
    Enter Annofab User ID: XXXXXX
    Enter Annofab Password:



優先順位
----------------------------------------------------------------
Annofabの認証情報の優先順位は以下の通りです。

* 環境変数
* .netrcファイル


エンドポイントURLの設定（開発者用）
==================================================================
環境変数 ``ANNOFAB_ENDPOINT_URL`` でAnnofab WebAPIのエンドポイントURLを設定することができます。
デフォルトは https://annofab.com です。

コマンドライン引数 ``--endpoint_url`` エンドポイントURLを指定することもできます。

.. code-block::

    $ annofabcli task list --endpoint_url http://localhost:8080
