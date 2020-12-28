FROM python:3.8

RUN pip install annofabcli -U && pip install annofabapi -U
# && apt-get update  \
# && apt-get install -y \
# && apt-get clean \
# && rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "annofabcli" ]
