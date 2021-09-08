=================================
project_member put
=================================

Description
=================================
プロジェクトメンバを登録します。



Examples
=================================

基本的な使い方
--------------------------
``--csv`` に、プロジェクトメンバ情報が記載されているCSVファイルを指定してください。
CSVファイルのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし
* 1列目: user_id（必須）
* 2列目: ロール（必須）
* 3列目: 抜取検査率
* 4列目: 抜取受入率


2列目のロールに指定できる値は以下の通りです。

* ``worker`` : アノテータ
* ``accepter`` : チェッカー
* ``training_data_user`` : アノテーションユーザ
* ``owner`` : プロジェクトオーナ


以下は、CSVファイルのサンプルです。

.. code-block::
    :caption: member.csv

    user1,worker
    user2,accepter,80,40


.. code-block::

    $ annofabcli project_member put --project_id prj1 --csv members.csv


CSVに記載されていないメンバを削除する場合は、``--delete`` を指定してください。

.. code-block::

    $ annofabcli project_member put --project_id prj1 --csv members.csv --delete

.. argparse::
   :ref: annofabcli.project_member.put_project_members.add_parser
   :prog: annofabcli project_member put
   :nosubcommands:
