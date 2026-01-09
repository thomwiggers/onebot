FROM python:3.14-slim

# Remove dangerous/unnecessary binaries and files to reduce attack surface
RUN rm -rf /usr/local/bin/pip* /usr/local/bin/easy_install* /usr/bin/apt* /usr/bin/dpkg*

WORKDIR /src
ADD entrypoint.py /src/entrypoint.py
RUN chmod 555 /src/entrypoint.py

# Switch to non-root user
USER nobody:nogroup

ENTRYPOINT ["/usr/local/bin/python3", "/src/entrypoint.py"]
CMD []