FROM python:3.13-slim

WORKDIR /opt/data-contract-monitor
COPY . /opt/data-contract-monitor
RUN python -m pip install --no-cache-dir .

ENV DCM_HOME=/data
VOLUME ["/data"]
EXPOSE 8765

ENTRYPOINT ["data-contract-monitor"]
CMD ["serve", "--host", "0.0.0.0", "--no-open-browser"]
