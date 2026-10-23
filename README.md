# annofab-cli
[Annofab](https://annofab.com/)のCLI(Command Line Interface)ツールです。

[![PyPI version](https://badge.fury.io/py/annofabcli.svg)](https://badge.fury.io/py/annofabcli)
[![Python Versions](https://img.shields.io/pypi/pyversions/annofabcli.svg)](https://pypi.org/project/annofabcli/)
[![Documentation Status](https://readthedocs.org/projects/annofab-cli/badge/?version=latest)](https://annofab-cli.readthedocs.io/ja/latest/?badge=latest)


* [Annofab](https://annofab.com/)
* [annofab-cliのドキュメント](https://annofab-cli.readthedocs.io/ja/latest/)
* [開発用ドキュメント](https://github.com/kurusugawa-computer/annofab-cli/blob/main/README_for_developer.md)



# 注意
* 作者または著作権者は、ソフトウェアに関してなんら責任を負いません。
* 予告なく互換性のない変更がある可能性をご了承ください。
* Annofabプロジェクトに大きな変更を及ぼすコマンドも存在します。間違えて実行してしまわないよう、注意してご利用ください。


## 廃止予定
https://annofab-cli.readthedocs.io/ja/latest/deprecations.html を参照してください。

## はじめに

以下のコマンドでインストールできます。

```
$ pip install annofabcli
```

動作環境、認証情報の設定、初回の動作確認は、[Getting Started](https://annofab-cli.readthedocs.io/ja/latest/user_guide/getting_started.html)を参照してください。

### eMudhra / emSign CA証明書のセキュリティ事象への対応

[Python公式の告知](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)に従い、利用している各Python環境（仮想環境を含む）でpipを26.2.2以上、certifiを2026.10.19以上に更新してください。pip自身が証明書を内蔵しているため、certifiだけの更新ではpipの対策は完了しません。

以下のコマンドは、告知に掲載されたSHA256で検証してpipを更新した後、certifiとannofabcliを更新します。

```bash
python -m pip install --upgrade "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
python -m pip install --upgrade "certifi>=2026.10.19" annofabcli
```

uvを利用する場合は、uvも0.13.4以上に更新してください。OSのCA証明書も更新し、コンテナを利用する場合はレイヤーキャッシュを無効にしてイメージを再ビルドしてください。

## Agent Skill

Codexでannofab-cliを利用するためのAgent Skillを提供しています。

インストール方法と利用上の注意は、[Agent Skill](https://annofab-cli.readthedocs.io/ja/latest/user_guide/agent_skill.html)を参照してください。
