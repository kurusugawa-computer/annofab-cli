=================================
instruction copy
=================================

Description
=================================
作業ガイドを別のプロジェクトにコピーします。



.. note::

    コピー元は ``--src_project_id``、コピー先は ``--dest_project_id`` で指定してください。
    以前の位置引数による指定は利用できません。

Examples
=================================

基本的な使い方
--------------------------


以下のコマンドは、プロジェクトprj1の作業ガイドをプロジェクトprj2にコピーします。

.. code-block::

    $ annofabcli instruction copy --src_project_id prj1 --dest_project_id prj2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.instruction.copy_instruction.add_parser
   :prog: annofabcli instruction copy
   :nosubcommands:
   :nodefaultconst:
