=================================
project_member diff
=================================

Description
=================================

左から右へのプロジェクトのメンバ構成の差分を出力します。メンバ情報は変更しません。
``--left_project_id`` に比較元、``--right_project_id`` に比較先のプロジェクトを指定します。
左右それぞれ1つのプロジェクトを指定します。
両プロジェクトの参照権限が必要です。オーナロールは不要です。

有効なメンバの所属、ロール、抜取検査率、抜取受入率を比較します。
脱退済みメンバは所属していないものとして扱います。
自分自身や組織外のユーザの差分も表示します。

* ``added`` : 右側にだけ所属するメンバ
* ``removed`` : 左側にだけ所属するメンバ
* ``changed`` : 両側に所属し、ロールや抜取率が異なるメンバ

:doc:`sync` は同期元から同期先へ構成を反映する操作です。
左側を同期元、右側を同期先にした場合、``removed`` のメンバを同期先に追加し、
``added`` のメンバを ``--delete_extra_members`` 指定時に脱退させます。
同期できないメンバの理由は ``sync`` 実行時のログで確認できます。

出力形式
=================================

:doc:`../annotation_specs/diff` と同じ4形式を指定できます。

* ``text`` : 差分項目をセクション見出し付きの階層形式で表示します。既定の形式です。
* ``detail_text`` : 変更された項目の値を ``changes`` 配下の ``left`` / ``right`` で表示します。
* ``json`` : 2つのプロジェクトの差分をJSONオブジェクトで出力します。
* ``pretty_json`` : JSONを整形して出力します。

JSONでは ``added_user_ids``、``removed_user_ids``、``changed_members`` に分類します。
変更されたメンバは、値が異なるプロパティだけを ``changes`` に出力します。
抜取率の ``null`` は、その値が未設定であることを示します。
差分がない場合はJSONの各リストが空になり、テキストでは出力を省略します。
テキストの差分がない場合、出力ファイルは空になります。

Examples
=================================

差分の概要を表示する
--------------------------

.. code-block::

    $ annofabcli project_member diff --left_project_id prj1 --right_project_id prj2

.. code-block:: text

    [project_members]
    left_project_id: prj1
    right_project_id: prj2
    added:
    - user2
    removed:
    - user3
    changed:
    - user_id: user1
      fields:
      - member_role
      - sampling_inspection_rate

変更された値を表示する
--------------------------

.. code-block::

    $ annofabcli project_member diff --left_project_id prj1 --right_project_id prj2 --format detail_text

.. code-block:: text

    [project_members]
    left_project_id: prj1
    right_project_id: prj2
    added:
    - user2
    removed:
    - user3
    changed:
    - user_id: user1
      changes:
        member_role:
          left: worker
          right: accepter
        sampling_inspection_rate:
          left: 10
          right: 20

JSONで出力する
--------------------------

.. code-block::

    $ annofabcli project_member diff --left_project_id prj1 --right_project_id prj2 --format pretty_json --output diff.json

.. code-block:: json

    {
      "left_project_id": "prj1",
      "right_project_id": "prj2",
      "added_user_ids": ["user2"],
      "removed_user_ids": ["user3"],
      "changed_members": [
        {
          "user_id": "user1",
          "changes": {
            "member_role": {"left": "worker", "right": "accepter"},
            "sampling_inspection_rate": {"left": 10, "right": 20}
          }
        }
      ]
    }


Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.diff_project_members.add_parser
   :prog: annofabcli project_member diff
   :nosubcommands:
   :nodefaultconst:
