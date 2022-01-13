==========================================
organization_member change
==========================================

Description
=================================
組織メンバの情報（ロールなど）を変更します。





Examples
=================================


基本的な使い方
--------------------------

対象組織の名前を ``--organization`` に、変更対象のユーザのuser_idを ``--user_id`` に指定します。
ロールを変更する場合は ``--role`` を指定します。


.. code-block::

    $ annofabcli organization_member change --organization org1 --user_id u1 u2 --role contributor


Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.change_organization_member.add_parser
   :prog: annofabcli organization_member change
   :nosubcommands:
   :nodefaultconst:
