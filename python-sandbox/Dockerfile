FROM python:latest
USER nobody:nogroup

ADD entrypoint.py /src/entrypoint.py

ENTRYPOINT ["/usr/bin/python3", "/src/entrypoint.py"]
CMD []
