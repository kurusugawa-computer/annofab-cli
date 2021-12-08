=================================
project_member change
=================================

Description
=================================

複数のプロジェクトメンバに対して、メンバ情報を変更します。自分自身は変更できません。


Examples
=================================

基本的な使い方
--------------------------
プロジェクトメンバのロールを変更する場合は、``--role`` を指定してください。指定できる値は以下の通りです。

* ``worker`` : アノテータ
* ``accepter`` : チェッカー
* ``training_data_user`` : アノテーションユーザ
* ``owner`` : プロジェクトオーナ


以下のコマンドは、ユーザuser1, user2をアノテータロールに変更します。

.. code-block::

    $ annofabcli project_member change --project_id prj1 --user_id user1 user2 --role worker


抜取検査率、抜取受入率を指定する場合は、``--member_info`` にJSON形式で値を指定してください。
以下のキーが使用できます。

* ``sampling_inspection_rate`` : 抜取検査率
* ``sampling_acceptance_rate`` : 抜取受入率

以下のコマンドは、ユーザuser1, user2の抜取検査率を10%、抜取受入率を20％に変更します。

.. code-block::
    
    $ annofabcli project_member change --project_id prj1 --user_id file://user_id.txt \
    --member_info '{"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}'


``--all_user`` を指定すると、 自分以外のすべてのプロジェクトメンバを変更します。
以下のコマンドは、自分以外のすべてのプロジェクトメンバを、アノテータロールに変更します。

.. code-block::

    $ annofabcli project_member change --project_id prj1 --all_user --role worker

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.change_project_members.add_parser
   :prog: annofabcli project_member change
   :nosubcommands:
   :nodefaultconst:
