=============================================
organization list_usage_detail
=============================================

Description
=================================
指定した月の組織の利用状況詳細CSVをダウンロードします。組織管理者として実行してください。

APIが提供するCSVファイルを、文字コードや列構成を変えずに保存します。
このコマンドはCSVのダウンロード専用です。
月別・日別の利用状況をCSVまたはJSONで出力する場合は、
:doc:`list_usage` を使用してください。出力例も同ページに記載しています。

Examples
=================================

.. code-block:: bash

    $ annofabcli organization list_usage_detail --organization org1 --month 2026-09 --output usage_detail.csv

年月の形式は :doc:`list_usage` と同じです。
出力先の親ディレクトリがない場合は作成します。
既存ファイルはダウンロード成功後に上書きします。
ダウンロードに失敗した場合は既存ファイルを保持し、不完全なCSVは残しません。

出力結果
=================================
指定した保存先に、APIから取得した利用状況詳細CSVが保存されます。

.. code-block:: text

    usage_detail.csv

詳細CSVの列構成はAnnofabが提供するファイルに従います。
``list_usage`` が生成する集計CSVとは異なります。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization.list_usage_detail.add_parser
   :prog: annofabcli organization list_usage_detail
   :nosubcommands:
   :nodefaultconst:
