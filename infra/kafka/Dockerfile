ARG KAFKA_IMAGE=apache/kafka:4.3.1
FROM ${KAFKA_IMAGE}

ARG JMX_EXPORTER_VERSION=1.5.0
ARG JMX_EXPORTER_SHA256=0315f3f657876302c6205a98d4036ec775dca529c5d0419ca60ee669c688239f

USER root
RUN mkdir -p /opt/bank/jmx && chown appuser:appuser /opt/bank/jmx
ADD --chown=appuser:appuser --chmod=0444 \
    --checksum=sha256:${JMX_EXPORTER_SHA256} \
    https://github.com/prometheus/jmx_exporter/releases/download/${JMX_EXPORTER_VERSION}/jmx_prometheus_javaagent-${JMX_EXPORTER_VERSION}.jar \
    /opt/bank/jmx/jmx_prometheus_javaagent.jar
USER appuser

