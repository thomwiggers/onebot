FROM python:slim
USER nobody:nogroup

ADD entrypoint.py /src/entrypoint.py

ENTRYPOINT ["/usr/local/bin/python3", "/src/entrypoint.py"]
CMD []
