ARG IMAGE=intersystems/irishealth-community:2026.2
FROM ${IMAGE}

WORKDIR /home/irisowner/dev

ENV IRISUSERNAME="_SYSTEM"
ENV IRISPASSWORD="SYS"
ENV IRISNAMESPACE="USER"
ENV PATH="/usr/irissys/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/irisowner/bin"
ENV PYTHONPATH="/home/irisowner/dev:/home/irisowner/dev/python"

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

RUN iris start IRIS && \
    iris session IRIS < iris.script > /tmp/kaggleloader-build.log 2>&1 && \
    cat /tmp/kaggleloader-build.log && \
    grep -Eq '^KAGGLELOADER_BUILD_OK=1[[:space:]]*$' /tmp/kaggleloader-build.log && \
    ! grep -Eq 'ERROR #|[<][A-Z][A-Z ]+[>]' /tmp/kaggleloader-build.log && \
    iris stop IRIS quietly
