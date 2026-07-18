# syntax=docker/dockerfile:1.7

ARG MINIO_MC_IMAGE
ARG CURL_IMAGE

FROM ${MINIO_MC_IMAGE} AS minio_client
FROM ${CURL_IMAGE}

USER root
COPY --from=minio_client /usr/bin/mc /usr/bin/mc

ENTRYPOINT ["mc"]
