=================================
project_member sync
=================================

Description
=================================

基準プロジェクトのメンバ構成を複数プロジェクトに同期します。
旧 ``project_member copy`` の代わりに使用してください。
基準プロジェクトの有効なメンバを追加し、既存メンバのロール・抜取検査率・抜取受入率を揃えます。
抜取率が未設定の場合は、同期先の設定も解除します。差分がないメンバは更新しません。
脱退済みのメンバは再登録します。

自分自身のメンバ情報は変更しません。
基準プロジェクトまたは同期先の組織に所属していないユーザは追加・更新しません。
この制約や処理の失敗により、完全一致しない場合があります。
基準プロジェクトの参照権限と、同期先プロジェクトのオーナロールが必要です。
同期前の差分は :doc:`diff` で確認してください。
``diff`` の左側に同期元、右側に同期先を指定すると、同期先の現在の構成との差分を確認できます。
``diff`` は左から右への変化を表示するため、同期による追加・脱退はその逆方向になります。

Examples
=================================

``--src_project_id`` に基準プロジェクト、``--dest_project_id`` に同期先を指定します。
同期先は複数指定でき、``file://`` で一覧ファイルも指定できます。
同期先ごとに変更内容の件数を表示し、確認後に同期します。
同期先で権限不足やHTTPエラーが発生した場合は、警告を出力して後続の同期先の処理を継続します。

.. code-block::

    $ annofabcli project_member sync --src_project_id prj1 --dest_project_id prj2 prj3

同期先にだけいるメンバも脱退させて構成の一致を目指す場合は、``--delete_extra_members`` を指定します。
省略時は、そのメンバを残します。自分自身は脱退させません。

.. code-block::

    $ annofabcli project_member sync --src_project_id prj1 --dest_project_id prj2 prj3 --delete_extra_members

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.sync_project_members.add_parser
   :prog: annofabcli project_member sync
   :nosubcommands:
   :nodefaultconst:
